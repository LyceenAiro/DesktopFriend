from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


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
