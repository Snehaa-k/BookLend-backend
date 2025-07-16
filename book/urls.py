from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, LoginViewSet, BookViewSet, BorrowViewSet, 
    ReviewViewSet, GenreViewSet, UserProfileViewSet
)

router = DefaultRouter()
router.register(r'books', BookViewSet)
router.register(r'borrows', BorrowViewSet, basename='borrow')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'genres', GenreViewSet)
router.register(r'profile', UserProfileViewSet, basename='profile')

urlpatterns = [
    path('register/', UserViewSet.as_view({'post': 'create'}), name='register'),
    path('login/', LoginViewSet.as_view({'post': 'create'}), name='login'),
    path('', include(router.urls)),
]