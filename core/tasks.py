from celery import shared_task 

@shared_task
def ping():
    print("Celery is alive")
    return "life's good"