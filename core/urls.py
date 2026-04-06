from django.urls import path
from . import views

urlpatterns = [
    # Single-page Divi assistant
    path('', views.assistant_view, name='home'),
    path('assistant/', views.assistant_view, name='assistant'),
    path('assistant/api/', views.assistant_message_api, name='assistant_api'),
    path('assistant/reset/', views.assistant_reset_api, name='assistant_reset_api'),
    path('assistant/ai-plan/', views.assistant_ai_plan_api, name='assistant_ai_plan_api'),

    # Optional handoff route
    path('human/', views.human_page, name='human_page'),
]