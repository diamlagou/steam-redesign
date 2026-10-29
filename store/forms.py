from django import forms

from .models import RefundRequest


class RefundForm(forms.ModelForm):
    class Meta:
        model = RefundRequest
        fields = ["method", "reason", "note"]
        widgets = {
            "method": forms.RadioSelect,
            "reason": forms.RadioSelect,
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "（選填）想補充的說明…"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].choices = RefundRequest.REASON_CHOICES
        self.fields["reason"].error_messages["required"] = "請選擇退款原因。"
