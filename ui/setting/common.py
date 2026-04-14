from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel


class StatusTag(QFrame):
    def __init__(self, text: str = "", level: str = "info", parent=None):
        super().__init__(parent)
        self.setObjectName("statusTag")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(0)

        self.label = QLabel(text)
        self.label.setObjectName("statusTagText")
        layout.addWidget(self.label)

        self.set_message(text, level)

    def set_message(self, text: str, level: str = "info") -> None:
        palette = {
            "success": ("#0f8a4a", "#ffffff"),
            "error": ("#b23c3c", "#ffffff"),
            "info": ("#1f5a9e", "#ffffff"),
            "muted": ("#3a3a3a", "#d8d8d8"),
        }
        background, foreground = palette.get(level, palette["info"])
        self.label.setText(text)
        self.setStyleSheet(
            "QFrame#statusTag {"
            f"background-color: {background};"
            "border: none;"
            "border-radius: 6px;"
            "}"
            "QLabel#statusTagText {"
            f"color: {foreground};"
            "font-size: 10px;"
            "font-weight: 600;"
            "letter-spacing: 0.2px;"
            "min-height: 14px;"
            "}"
        )


def create_section_card(title: str, hint: str) -> QFrame:
    card = QFrame()
    card.setObjectName("sectionCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(18, 16, 18, 16)
    card_layout.setSpacing(14)

    section_title = QLabel(title)
    section_title.setObjectName("sectionTitle")
    card_layout.addWidget(section_title)

    section_hint = QLabel(hint)
    section_hint.setObjectName("sectionHint")
    card_layout.addWidget(section_hint)

    return card
