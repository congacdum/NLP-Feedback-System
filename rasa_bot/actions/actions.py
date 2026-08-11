from __future__ import annotations

import os
import re

import requests
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

APP_URL = os.getenv("APP_INTERNAL_URL", "http://app:8000")
ASPECT_VI = {"product_quality": "chất lượng sản phẩm", "delivery": "giao hàng", "customer_service": "hỗ trợ của shop", "packaging": "đóng gói", "price": "giá cả", "other": "nội dung khác"}
SENTIMENT_VI = {"positive": "hài lòng", "neutral": "trung tính", "negative": "chưa hài lòng", "mixed": "vừa hài lòng vừa chưa hài lòng"}
RATING = re.compile(r"(?<!\d)([1-5])(?!\d)")


def is_affirmed(text: str) -> bool:
    return text.casefold().strip() in {"có", "đúng", "đúng rồi", "ok", "ừ", "yes", "đồng ý"}


def is_denied(text: str) -> bool:
    return text.casefold().strip() in {"không", "không đúng", "ko", "no", "chưa"}


class ActionAnalyzeFeedback(Action):
    def name(self) -> str:
        return "action_analyze_feedback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        text = tracker.latest_message.get("text", "").strip()
        try:
            result = requests.post(APP_URL + "/api/nlp/analyze", json={"text": text}, timeout=3).json()
            aspects = result.get("aspects", [])
        except Exception:
            dispatcher.utter_message(text="Mình đã nhận nội dung, nhưng phần phân tích đang tạm thời không phản hồi. Bạn vẫn có thể gửi đánh giá qua trang sản phẩm để hệ thống lưu phản hồi.")
            return []
        if not aspects:
            dispatcher.utter_message(text="Mình muốn hiểu đúng hơn: bạn đang nói chủ yếu về sản phẩm, giao hàng, đóng gói, giá cả hay hỗ trợ của shop?")
            return [SlotSet("feedback_text", text), SlotSet("needs_clarification", True), SlotSet("detected_aspects", [])]
        summary = "; ".join(f"{ASPECT_VI.get(item['aspect'], item['aspect'])} {SENTIMENT_VI.get(item['sentiment'], item['sentiment'])}" for item in aspects)
        dispatcher.utter_message(text=f"Mình hiểu bạn đang nhận xét về {summary}. Mình hiểu đúng chứ?")
        return [SlotSet("feedback_text", text), SlotSet("detected_aspects", aspects), SlotSet("needs_clarification", False), SlotSet("feedback_confirmed", False)]


class ActionConfirmFeedback(Action):
    def name(self) -> str:
        return "action_confirm_feedback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        text = tracker.latest_message.get("text", "")
        if tracker.get_slot("wants_support") is True and tracker.get_slot("contact_consent") is None:
            if is_affirmed(text):
                dispatcher.utter_message(text="Cảm ơn bạn đã đồng ý. Bạn có thể để lại email hoặc số điện thoại để shop liên hệ.")
                return [SlotSet("contact_consent", True)]
            if is_denied(text):
                dispatcher.utter_message(text="Mình đã ghi nhận phản hồi mà không lưu thông tin liên hệ. Cảm ơn bạn.")
                return [SlotSet("contact_consent", False)]
        if tracker.get_slot("feedback_confirmed") is True and tracker.get_slot("rating") is not None and is_denied(text):
            dispatcher.utter_message(text="Mình đã ghi nhận phản hồi. Cảm ơn bạn đã dành thời gian chia sẻ.")
            return [SlotSet("wants_support", False)]
        if is_affirmed(text):
            if tracker.get_slot("rating") is None:
                dispatcher.utter_message(text="Cảm ơn bạn. Bạn muốn chấm sản phẩm bao nhiêu sao từ 1 đến 5?")
            else:
                dispatcher.utter_message(text="Cảm ơn bạn đã xác nhận. Nếu bạn cần shop hỗ trợ thêm, hãy cho mình biết.")
            return [SlotSet("feedback_confirmed", True)]
        if is_denied(text):
            dispatcher.utter_message(text="Cảm ơn bạn đã chỉnh lại. Bạn có thể mô tả cụ thể hơn để mình ghi nhận chính xác không?")
            return [SlotSet("feedback_confirmed", False), SlotSet("needs_clarification", True)]
        dispatcher.utter_message(text="Bạn xác nhận giúp mình là đúng hay chưa đúng nhé.")
        return []


class ActionCaptureRating(Action):
    def name(self) -> str:
        return "action_capture_rating"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        text = tracker.latest_message.get("text", "")
        entity = next((entity.get("value") for entity in tracker.latest_message.get("entities", []) if entity.get("entity") == "rating"), None)
        match = RATING.search(str(entity or text))
        if not match:
            dispatcher.utter_message(text="Bạn cho mình một mức từ 1 đến 5 sao nhé.")
            return []
        rating = int(match.group(1))
        dispatcher.utter_message(text="Cảm ơn bạn đã chấm %s sao. Bạn có cần shop hỗ trợ thêm không?" % rating)
        return [SlotSet("rating", rating)]


class ActionHandleSupport(Action):
    def name(self) -> str:
        return "action_handle_support"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        text = tracker.latest_message.get("text", "")
        if is_denied(text):
            dispatcher.utter_message(text="Mình đã ghi nhận phản hồi. Cảm ơn bạn đã dành thời gian chia sẻ.")
            return [SlotSet("wants_support", False)]
        dispatcher.utter_message(text="Bạn có đồng ý để shop liên hệ về yêu cầu hỗ trợ này không? Bạn có thể trả lời Có hoặc Không.")
        return [SlotSet("wants_support", True)]


class ActionCaptureContact(Action):
    def name(self) -> str:
        return "action_capture_contact"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        contact = next((entity.get("value") for entity in tracker.latest_message.get("entities", []) if entity.get("entity") == "contact"), None)
        if not contact and tracker.get_slot("contact_consent") is True and tracker.latest_message.get("text", "").strip().casefold() not in {"bỏ qua", "bo qua", "skip"}:
            contact = tracker.latest_message.get("text", "").strip()
        if not contact:
            dispatcher.utter_message(text="Mình chỉ lưu thông tin liên hệ khi bạn đồng ý. Bạn có thể gửi email/số điện thoại hoặc bỏ qua.")
            return [SlotSet("contact_consent", False)]
        dispatcher.utter_message(text="Cảm ơn bạn. Shop sẽ dùng thông tin này chỉ để phản hồi yêu cầu hỗ trợ của bạn.")
        return [SlotSet("contact_consent", True), SlotSet("contact", str(contact))]
