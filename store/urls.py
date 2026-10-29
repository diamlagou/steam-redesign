from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("search/", views.search, name="search"),
    path("game/<int:pk>/", views.game_detail, name="game_detail"),
    path("game/<int:pk>/add/", views.add_to_library, name="add_to_library"),
    path("library/", views.library, name="library"),
    path("library/<int:pk>/refund/", views.refund_request, name="refund_request"),
    path("refund/<int:pk>/done/", views.refund_done, name="refund_done"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="store/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
]
