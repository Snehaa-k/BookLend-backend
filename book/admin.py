from django.contrib import admin
from .models import Book, Genre, Borrow, Review

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'genre', 'available', 'read_count', 'average_rating']
    list_filter = ['genre', 'available', 'created_at']
    search_fields = ['title', 'author', 'isbn']
    readonly_fields = ['read_count', 'created_at', 'updated_at']

@admin.register(Borrow)
class BorrowAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'borrowed_on', 'returned', 'returned_on']
    list_filter = ['returned', 'borrowed_on']
    search_fields = ['user__username', 'book__title']
    readonly_fields = ['borrowed_on']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'book__title', 'comment']
    readonly_fields = ['created_at', 'updated_at']
