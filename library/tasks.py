import logging
from celery import shared_task
from .models import Loan
from django.core import mail
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass

@shared_task
def check_overdue_loans():
    overdue_loans = Loan.objects.select_related("book", "member", "member__user").filter(is_returned=False, due_date__lt=timezone.now().date())

    connection = mail.get_connection()
    messages = []
    for loan in overdue_loans:
        mail_message = mail.EmailMessage(
            subject="Overdue Loans",
            body=f"Hello {loan.member.user}, \n\n You have overdue loan of {loan.book.title} as of {loan.due_date}. Please return it ASAP.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[loan.member.user.email],
            connection=connection
        )
        messages.append(mail_message)

    connection.send_messages(messages)
    print("Notified member for overdue loans")