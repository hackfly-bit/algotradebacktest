from apps.marketdata.models import Dataset


def latest_dataset(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"latest_dataset": None}
    return {"latest_dataset": Dataset.objects.only("id", "source_name").order_by("-created_at").first()}
