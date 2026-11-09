from django import forms

from .models import Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('title', 'text', 'image')
        labels = {'title': '제목', 'text': '내용', 'image': '이미지'}
