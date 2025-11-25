import io
import os
import zipfile
import tempfile
from datetime import datetime
from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.core.management import call_command
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from .models import *
from django.conf import settings
import subprocess

# Register your models here.

admin.site.site_header="Sistema ITCG"
admin.site.site_title="Sistema Gestor de Biblioteca"
admin.site.index_title="Administración Biblioteca"
ADMIN_GROUP_NAME = 'Bibliotecarios_Admin' 

class MyAdminSite(AdminSite):
    site_header = 'Administración - Biblioteca'

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('backup-db/', self.admin_view(self.backup_db_view), name='backup-db'),
            path('restore-db/', self.admin_view(self.restore_db_view), name='restore-db'),
        ]
        return my_urls + urls

    def _get_mysql_settings(self):
        """Extrae host, port, user, password, dbname desde settings.DATABASES['default']"""
        db = settings.DATABASES.get('default', {})
        engine = db.get('ENGINE', '')
        if 'mysql' not in engine:
            raise RuntimeError("La base de datos configurada no es MySQL.")
        host = db.get('HOST') or 'localhost'
        port = str(db.get('PORT') or 3306)
        user = db.get('USER') or ''
        password = db.get('PASSWORD') or ''
        name = db.get('NAME') or ''
        return host, port, user, password, name

    def backup_db_view(self, request):
        # Seguridad: solo superuser o grupo admin
        user = request.user
        if not (user.is_authenticated and (user.is_superuser or user.groups.filter(name=ADMIN_GROUP_NAME).exists())):
            return HttpResponseForbidden("No tienes permiso para generar respaldos.")

        # Obtener conexión MySQL desde settings
        try:
            host, port, dbuser, dbpass, dbname = self._get_mysql_settings()
        except RuntimeError as e:
            messages.error(request, str(e))
            return HttpResponseRedirect(reverse(f'{self.name}:index'))

        # Construir comando mysqldump
        # Nota: usar --single-transaction y --quick para grandes tablas
        mysqldump_cmd = [
            'mysqldump',
            '-h', host,
            '-P', port,
            '-u', dbuser,
            f'--password={dbpass}',
            '--single-transaction',
            '--quick',
            dbname,
        ]

        # Ejecutar comando y capturar stdout
        try:
            proc = subprocess.Popen(mysqldump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()
            if proc.returncode != 0:
                err_text = err.decode('utf-8', errors='ignore')
                messages.error(request, f"mysqldump falló: {err_text}")
                return HttpResponseRedirect(reverse(f'{self.name}:index'))
        except FileNotFoundError:
            messages.error(request, "mysqldump no encontrado. Instala el cliente MySQL y asegúrate de que 'mysqldump' esté en PATH.")
            return HttpResponseRedirect(reverse(f'{self.name}:index'))
        except Exception as e:
            messages.error(request, f"Error ejecutando mysqldump: {e}")
            return HttpResponseRedirect(reverse(f'{self.name}:index'))

        # Preparar respuesta como descarga (posible zip)
        filename_sql = f'backup-{dbname}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.sql'
        # Si prefieres comprimir:
        # crear zip en memoria
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(filename_sql, out)
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="backup-{dbname}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip"'
        return response

    def restore_db_view(self, request):
        """
        Restaurar base a partir de un archivo .sql (o .zip con .sql dentro).
        Método: guardar archivo temporal y ejecutar 'mysql' pasando el sql por stdin.
        """
        user = request.user
        if not (user.is_authenticated and (user.is_superuser or user.groups.filter(name=ADMIN_GROUP_NAME).exists())):
            return HttpResponseForbidden("No tienes permiso para restaurar respaldos.")

        if request.method != 'POST':
            return HttpResponseRedirect(reverse(f'{self.name}:index'))

        # archivo subido
        uploaded = request.FILES.get('backup_file')
        if not uploaded:
            messages.error(request, "No se envió ningún archivo.")
            return HttpResponseRedirect(reverse(f'{self.name}:index'))

        # validar extensión
        filename = uploaded.name.lower()
        if not (filename.endswith('.sql') or filename.endswith('.zip')):
            messages.error(request, "Formato no soportado. Sube .sql o .zip que contenga .sql.")
            return HttpResponseRedirect(reverse(f'{self.name}:index'))

        try:
            host, port, dbuser, dbpass, dbname = self._get_mysql_settings()
        except RuntimeError as e:
            messages.error(request, str(e))
            return HttpResponseRedirect(reverse(f'{self.name}:index'))

        # Guardar archivo temporal
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tf:
                for chunk in uploaded.chunks():
                    tf.write(chunk)
                tmp_path = tf.name

            sql_files = []

            # Si es zip, extraer archivos .sql
            if zipfile.is_zipfile(tmp_path) or filename.endswith('.zip'):
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    for member in zf.namelist():
                        if member.lower().endswith('.sql'):
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.sql') as ef:
                                ef.write(zf.read(member))
                                sql_files.append(ef.name)
                if not sql_files:
                    raise ValueError("El ZIP no contiene archivos .sql")
            else:
                sql_files = [tmp_path]

            # Ejecutar mysql < archivo.sql para cada sql
            for sql in sql_files:
                # comando sin shell: pasamos el archivo como stdin
                mysql_cmd = [
                    'mysql',
                    '-h', host,
                    '-P', port,
                    '-u', dbuser,
                    f'--password={dbpass}',
                    dbname,
                ]
                try:
                    with open(sql, 'rb') as infile:
                        proc = subprocess.Popen(mysql_cmd, stdin=infile, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        out, err = proc.communicate()
                        if proc.returncode != 0:
                            err_text = err.decode('utf-8', errors='ignore')
                            raise RuntimeError(f"mysql falló al importar {os.path.basename(sql)}: {err_text}")
                except FileNotFoundError:
                    raise RuntimeError("El cliente 'mysql' no se encontró. Instala MySQL client y añade 'mysql' al PATH.")
            messages.success(request, "Restauración completada correctamente.")
        except Exception as e:
            messages.error(request, f"Error durante la restauración: {e}")
        finally:
            # limpiar archivos temporales
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except:
                pass
            # borrar extraídos
            # (si los sql_files no están en tmp_path y existen, eliminarlos)
            try:
                for f in sql_files:
                    if os.path.exists(f):
                        os.remove(f)
            except:
                pass

        return HttpResponseRedirect(reverse(f'{self.name}:index'))

    # Si ya tienes index override, mantén y añade contexto si quieres
    def index(self, request, extra_context=None):
        extra = extra_context or {}
        extra.update({'mysql_restore_help': 'Sube un .sql (o .zip con .sql) para restaurar la BD.'})
        return super().index(request, extra_context=extra)

# instancia del admin
custom_admin_site = MyAdminSite(name='custom_admin')

# registrar User/Group en custom_admin_site si usas admin personalizado
from django.contrib.auth.admin import UserAdmin, GroupAdmin
try:
    custom_admin_site.register(User, UserAdmin)
except admin.sites.AlreadyRegistered:
    pass
try:
    custom_admin_site.register(Group, GroupAdmin)
except admin.sites.AlreadyRegistered:
    pass


#admin.site.register(Carrera)
@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('id_carrera', 'nombre')
    list_filter = ('id_carrera', 'nombre')
    search_fields = ('id_carrera', 'nombre')
    ordering = ('id_carrera', 'nombre')


#admin.site.register(Alumno)
custom_admin_site.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('id_alumno', 'nombre', 'semestre', 'carrera')
    list_filter = ('semestre', 'carrera')
    search_fields = ('id_alumno', 'nombre', 'carrera__nombre')
    raw_id_fields = ('carrera',)
    ordering = ('id_alumno', 'nombre') 


#admin.site.register(Autor)
custom_admin_site.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ('id_autor', 'nombre', 'nacionalidad')
    list_filter = ('nombre', 'nacionalidad')
    search_fields = ('id_autor', 'nombre', 'nacionalidad')
    ordering = ('id_autor', 'nombre')

#admin.site.register(Editorial)
custom_admin_site.register(Editorial)
class EditorialAdmin(admin.ModelAdmin):
    list_display = ('id_editorial', 'nombre', 'pais')
    list_filter = ('nombre', 'pais')
    search_fields = ('id_editorial', 'nombre', 'pais')
    ordering = ('id_editorial', 'nombre')

#admin.site.register(Categoria)
custom_admin_site.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id_categoria', 'nombre')
    list_filter = ('nombre',)
    search_fields = ('id_categoria', 'nombre')
    ordering = ('id_categoria', 'nombre')
    
#admin.site.register(Libro)
custom_admin_site.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = ('id_libro', 'titulo', 'autor', 'categoria', 'editorial', 'anio_publicacion')
    list_filter = ('categoria', 'autor', 'editorial', 'anio_publicacion')
    search_fields = ('id_libro', 'titulo', 'autor__nombre', 'categoria__nombre', 'editorial__nombre')
    raw_id_fields = ('autor', 'categoria', 'editorial')
    ordering = ('id_libro', 'titulo')

#admin.site.register(Prestamo)
@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ('id_prestamo', 'libro', 'alumno', 'fecha_prestamo', 'fecha_devolucion')
    list_filter = ('libro', 'fecha_prestamo', 'fecha_devolucion')
    search_fields = ('id_prestamo', 'libro__titulo', 'alumno__nombre')
    raw_id_fields = ('libro', 'alumno')
    ordering = ('id_prestamo', 'fecha_prestamo')

#admin.site.register(Sancion)
custom_admin_site.register(Sancion)
class SancionAdmin(admin.ModelAdmin):
    list_display = ('id_sancion', 'alumno', 'motivo', 'fecha', 'fecha_fin')
    list_filter = ('alumno', 'motivo', 'fecha', 'fecha_fin')
    search_fields = ('id_sancion', 'alumno__nombre', 'motivo')
    raw_id_fields = ('alumno',)
    ordering = ('id_sancion', 'fecha')

#admin.site.register(Usuario)
custom_admin_site.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_usuario', 'nombre')
    list_filter = ('nombre',)
    search_fields = ('id_usuario', 'nombre')
    ordering = ('id_usuario', 'nombre')

#admin.site.register(Historial)
custom_admin_site.register(Historial)
class HistorialAdmin(admin.ModelAdmin):
    list_display = ('id_historial', 'alumno', 'libro', 'fecha_prestamo', 'fecha_devolucion')
    list_filter = ('fecha_prestamo', 'fecha_devolucion')
    search_fields = ('id_historial', 'alumno__nombre', 'libro__titulo')
    raw_id_fields = ('alumno', 'libro')
    ordering = ('id_historial', 'fecha_prestamo')