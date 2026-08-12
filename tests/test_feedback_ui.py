from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_customer_feedback_panel_renders_reply_not_model_labels():
    template = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    script = (ROOT / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "data-feedback-conversation" in template
    assert "data-feedback-customer-message" in template
    assert "data-feedback-status" in template
    assert "data-feedback-scroll-area" in template
    assert "data-feedback-analysis" not in template
    assert "renderFeedbackAnalysis" not in script
    assert "aspectLabels" not in script
    assert "sentimentLabels" not in script
    assert "renderCustomerFeedback" in script
    assert "assistant_message" in script
    assert "scrollTop = feedbackScrollArea.scrollHeight" in script
