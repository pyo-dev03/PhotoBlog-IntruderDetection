from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'author', 'source', 'labels', 'device', 'acknowledged',
                    'published_date')
    list_filter = ('source', 'acknowledged', 'device')
    search_fields = ('title', 'text', 'labels')
    readonly_fields = ('thumbnail', 'updated_date', 'labels')
