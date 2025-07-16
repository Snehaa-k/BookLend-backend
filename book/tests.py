from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Book, Genre, Borrow, Review

class BookLendingAPITestCase(APITestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test genre
        self.genre = Genre.objects.create(name='Fiction')
        
        # Create test book
        self.book = Book.objects.create(
            title='Test Book',
            author='Test Author',
            genre=self.genre,
            description='A test book'
        )
        
        # Get JWT token
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        
    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
    
    def test_user_registration(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123'
        }
        response = self.client.post('/api/register/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
    
    def test_user_login(self):
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post('/api/login/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_book_list(self):
        response = self.client.get('/api/books/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_book_borrow(self):
        self.authenticate()
        response = self.client.post(f'/api/books/{self.book.id}/borrow/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check book is no longer available
        self.book.refresh_from_db()
        self.assertFalse(self.book.available)
    
    def test_book_return(self):
        # First borrow the book
        self.authenticate()
        Borrow.objects.create(user=self.user, book=self.book)
        self.book.available = False
        self.book.save()
        
        # Then return it
        response = self.client.post(f'/api/books/{self.book.id}/return_book/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check book is available again
        self.book.refresh_from_db()
        self.assertTrue(self.book.available)
    
    def test_book_recommendations(self):
        self.authenticate()
        response = self.client.get('/api/books/recommendations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('books', response.data)
    
    def test_create_review(self):
        # User must borrow book first
        Borrow.objects.create(user=self.user, book=self.book)
        
        self.authenticate()
        data = {
            'book': self.book.id,
            'rating': 5,
            'comment': 'Great book!'
        }
        response = self.client.post('/api/reviews/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_user_stats(self):
        self.authenticate()
        response = self.client.get('/api/profile/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_books_borrowed', response.data)

class ModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.genre = Genre.objects.create(name='Fiction')
        self.book = Book.objects.create(
            title='Test Book',
            author='Test Author',
            genre=self.genre
        )
    
    def test_book_average_rating(self):
        # Create reviews
        Review.objects.create(user=self.user, book=self.book, rating=4)
        Review.objects.create(
            user=User.objects.create_user(username='user2', password='pass'),
            book=self.book,
            rating=5
        )
        
        self.assertEqual(self.book.average_rating, 4.5)
    
    def test_borrow_constraint(self):
        # User can't borrow same book twice without returning
        Borrow.objects.create(user=self.user, book=self.book)
        
        with self.assertRaises(Exception):
            Borrow.objects.create(user=self.user, book=self.book)
