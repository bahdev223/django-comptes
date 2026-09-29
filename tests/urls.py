from django.urls import include, path

urlpatterns = [
    path("api/", include("comptes.urls_api")),
    path(
        "finance/",
        include(("comptes.urls", "comptes"), namespace="comptes"),
    ),
]
