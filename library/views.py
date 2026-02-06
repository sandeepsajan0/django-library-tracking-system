from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Count
from .tasks import send_loan_notification, check_overdue_loans

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("author").all()
    serializer_class = BookSerializer

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['GET'])
    def top_active_members(self, request):
        members = Member.objects.prefetch_related("loans").select_related("users").all().annotate(
            loans_count=Count("loans")
        ).order_by("-loans_count")
        if members:
            serializer = MemberSerializer(members[:5], many=True)
            return Response(data=serializer.data, status=status.HTTP_200_OK)
        return Response({"status": "No members found"}, status=status.HTTP_404_NOT_FOUND)


class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'])
    def extend_due_date(self, request, pk):
        loan = self.get_object()
        if loan.due_date < timezone.now().date():
            return Response({"status": "Loan is already overdue"}, status=status.HTTP_403_FORBIDDEN)
        additional_days = request.data.get('additional_days')
        loan.due_date += timezone.timedelta(days=additional_days)
        loan.save(update_fields={"due_date"})
        serializer = LoanSerializer(loan)
        return Response({"status": "Due date extended successfully", "data": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="notify-overdue-loans")
    def notify_overdue_loan_members(self, request):
        check_overdue_loans.delay()
        return Response({"status": "Notified Members for overdue loan"}, status=status.HTTP_200_OK)
