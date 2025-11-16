from django.contrib import admin
from .models import *

# Register your models here.

admin.site.site_header="Sistema ITCG"
admin.site.site_title="Sistema Gestor de Biblioteca"
admin.site.index_title="Administración Biblioteca"

#admin.site.register(Carrera)
@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('id_carrera', 'nombre')
    list_filter = ('id_carrera', 'nombre')
    search_fields = ('id_carrera', 'nombre')
    ordering = ('id_carrera', 'nombre')


#admin.site.register(Alumno)
@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('id_alumno', 'nombre', 'semestre', 'carrera')
    list_filter = ('semestre', 'carrera')
    search_fields = ('id_alumno', 'nombre', 'carrera__nombre')
    raw_id_fields = ('carrera',)
    ordering = ('id_alumno', 'nombre') 


#admin.site.register(Autor)
@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ('id_autor', 'nombre', 'nacionalidad')
    list_filter = ('nombre', 'nacionalidad')
    search_fields = ('id_autor', 'nombre', 'nacionalidad')
    ordering = ('id_autor', 'nombre')

#admin.site.register(Editorial)
@admin.register(Editorial)
class EditorialAdmin(admin.ModelAdmin):
    list_display = ('id_editorial', 'nombre', 'pais')
    list_filter = ('nombre', 'pais')
    search_fields = ('id_editorial', 'nombre', 'pais')
    ordering = ('id_editorial', 'nombre')

#admin.site.register(Categoria)
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id_categoria', 'nombre')
    list_filter = ('nombre',)
    search_fields = ('id_categoria', 'nombre')
    ordering = ('id_categoria', 'nombre')
    
#admin.site.register(Libro)
@admin.register(Libro)
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
@admin.register(Sancion)
class SancionAdmin(admin.ModelAdmin):
    list_display = ('id_sancion', 'alumno', 'motivo', 'fecha', 'fecha_fin')
    list_filter = ('alumno', 'motivo', 'fecha', 'fecha_fin')
    search_fields = ('id_sancion', 'alumno__nombre', 'motivo')
    raw_id_fields = ('alumno',)
    ordering = ('id_sancion', 'fecha')

#admin.site.register(Usuario)
@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_usuario', 'nombre')
    list_filter = ('nombre',)
    search_fields = ('id_usuario', 'nombre')
    ordering = ('id_usuario', 'nombre')

#admin.site.register(Historial)
@admin.register(Historial)
class HistorialAdmin(admin.ModelAdmin):
    list_display = ('id_historial', 'alumno', 'libro', 'fecha_prestamo', 'fecha_devolucion')
    list_filter = ('fecha_prestamo', 'fecha_devolucion')
    search_fields = ('id_historial', 'alumno__nombre', 'libro__titulo')
    raw_id_fields = ('alumno', 'libro')
    ordering = ('id_historial', 'fecha_prestamo')