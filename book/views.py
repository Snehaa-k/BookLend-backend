from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from .models import Book, Genre, Borrow, Review
from .serializers import *
from rest_framework_simplejwt.tokens import RefreshToken

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'message': 'User registered successfully'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    
    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'message': 'Login successful'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related('genre').prefetch_related('reviews')
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['genre__name', 'author', 'available']
    search_fields = ['title', 'author', 'description']
    ordering_fields = ['read_count', 'title', 'created_at']
    ordering = ['-created_at']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'list':
            return BookListSerializer
        elif self.action == 'create':
            return BookCreateSerializer
        return BookSerializer

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def borrow(self, request, pk=None):
        book = self.get_object()

        if not book.available:
            return Response({"error": "Book not available"}, status=status.HTTP_400_BAD_REQUEST)

        if Borrow.objects.filter(user=request.user, book=book, returned=False).exists():
            return Response({"error": "You already borrowed this book"}, status=status.HTTP_400_BAD_REQUEST)

        borrow = Borrow.objects.create(user=request.user, book=book)
        book.available = False
        book.read_count += 1
        book.save()
        
        return Response({
            "message": "Book borrowed successfully",
            "borrow_id": borrow.id,
            "borrowed_on": borrow.borrowed_on
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def return_book(self, request, pk=None):
        try:
            borrow = Borrow.objects.get(user=request.user, book_id=pk, returned=False)
            borrow.returned = True
            borrow.returned_on = timezone.now()
            borrow.save()

            book = borrow.book
            book.available = True
            book.save()

            return Response({
                "message": "Book returned successfully",
                "returned_on": borrow.returned_on,
                "days_borrowed": (borrow.returned_on - borrow.borrowed_on).days
            }, status=status.HTTP_200_OK)
        except Borrow.DoesNotExist:
            return Response({"error": "You haven't borrowed this book or already returned it"}, 
                          status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def recommendations(self, request):
        user = request.user
        borrowed = Borrow.objects.filter(user=user).select_related('book__genre')

        if borrowed.exists():
            genre_ids = borrowed.values_list('book__genre', flat=True).distinct()
            borrowed_book_ids = borrowed.values_list('book', flat=True)
            
            recommended_books = Book.objects.filter(
                genre__in=genre_ids,
                available=True
            ).exclude(
                id__in=borrowed_book_ids
            ).annotate(
                avg_rating=Avg('reviews__rating')
            ).order_by('-read_count', '-avg_rating')[:5]
        else:
            recommended_books = Book.objects.filter(
                available=True
            ).annotate(
                avg_rating=Avg('reviews__rating')
            ).order_by('-read_count', '-avg_rating')[:5]

        serializer = BookListSerializer(recommended_books, many=True)
        return Response({
            "message": "Book recommendations based on your reading history" if borrowed.exists() 
                      else "Popular book recommendations",
            "books": serializer.data
        })

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        book = self.get_object()
        reviews = Review.objects.filter(book=book).select_related('user')
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

class BorrowViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BorrowSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Borrow.objects.filter(user=self.request.user).select_related('book', 'book__genre')
        
        returned = self.request.query_params.get('returned', None)
        if returned is not None:
            queryset = queryset.filter(returned=returned.lower() == 'true')
        else:
            queryset = queryset.filter(returned=False)
            
        return queryset.order_by('-borrowed_on')

    @action(detail=False, methods=['get'])
    def history(self, request):
        borrows = Borrow.objects.filter(user=request.user).select_related('book', 'book__genre').order_by('-borrowed_on')
        page = self.paginate_queryset(borrows)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(borrows, many=True)
        return Response(serializer.data)

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Review.objects.select_related('user', 'book')
        
        book_id = self.request.query_params.get('book', None)
        if book_id:
            queryset = queryset.filter(book_id=book_id)
            
        my_reviews = self.request.query_params.get('my_reviews', None)
        if my_reviews and my_reviews.lower() == 'true':
            queryset = queryset.filter(user=self.request.user)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        book = serializer.validated_data['book']
        if not Borrow.objects.filter(user=self.request.user, book=book).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("You can only review books you have borrowed")
        
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only edit your own reviews")
        serializer.save()

class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['get'])
    def books(self, request, pk=None):
        genre = self.get_object()
        books = Book.objects.filter(genre=genre).select_related('genre').prefetch_related('reviews')
        
        page = self.paginate_queryset(books)
        if page is not None:
            serializer = BookListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = BookListSerializer(books, many=True)
        return Response(serializer.data)

class UserProfileViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        user = request.user
        
        total_borrowed = Borrow.objects.filter(user=user).count()
        currently_borrowed = Borrow.objects.filter(user=user, returned=False).count()
        total_returned = Borrow.objects.filter(user=user, returned=True).count()
        total_reviews = Review.objects.filter(user=user).count()
        
        favorite_genres = Borrow.objects.filter(user=user).values(
            'book__genre__name'
        ).annotate(
            count=Count('book__genre')
        ).order_by('-count')[:3]
        
        return Response({
            'total_books_borrowed': total_borrowed,
            'currently_borrowed': currently_borrowed,
            'books_returned': total_returned,
            'reviews_written': total_reviews,
            'favorite_genres': list(favorite_genres)
        })