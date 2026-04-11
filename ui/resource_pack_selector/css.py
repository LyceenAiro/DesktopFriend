LIST_ITEM_STYLE = """
ResourcePackListItem {
    background-color: transparent;
    border: none;
}
"""

DELETE_BUTTON_STYLE = """
#deleteButton {
    color: #e05050;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    font-size: 12px;
    padding: 0px;
    margin: 0px;
}
"""

RESOURCE_PACK_SELECTOR_STYLE = """
QDialog {
    background: transparent;
}
#windowShell {
    background-color: #1f1f1f;
    border: 1px solid #3a3a3a;
    border-radius: 16px;
}
#leftPanel {
    background:qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2c2c2c,
        stop:1 #1f1f1f);
    border-right: 1px solid #3a3a3a;
    border-top-left-radius: 16px;
    border-bottom-left-radius: 16px;
}
#rightPanel {
    background-color: #262626;
    border-top-right-radius: 16px;
    border-bottom-right-radius: 16px;
}
#brandTitle {
    color: #f3f3f3;
    font-size: 30px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
#brandSubtitle {
    color: #f95f53;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1.4px;
    text-transform: uppercase;
}
#brandDescription {
    color: #d0d0d0;
    font-size: 13px;
    line-height: 1.4em;
}
#brandHint {
    color: #9a9a9a;
    font-size: 11px;
}
#title {
    color: #f5f5f5;
    font-size: 22px;
    font-weight: 650;
}
#previewTitle {
    color: #d7d7d7;
    font-size: 12px;
    font-weight: 600;
    padding-top: 2px;
}
#previewBox {
    background-color: #1d1d1d;
    border: 1px solid #3c3c3c;
    border-radius: 8px;
    color: #9a9a9a;
    font-size: 12px;
}
#info {
    color: #b8b8b8;
    font-size: 12px;
    padding-bottom: 2px;
}
#packList {
    background-color: transparent;
    border: none;
    border-radius: 0;
    color: #f0f0f0;
    outline: none;
    font-size: 13px;
    padding: 6px;
}
#listContainer {
    background-color: #1f1f1f;
    border: 1px solid #3c3c3c;
    border-radius: 8px;
}
#packList::item {
    height: 40px;
    margin: 2px 4px;
    padding: 0px;
    border-radius: 6px;
}
#packList::item:hover {
    background-color: transparent;
    border: none;
}
#packList::item:selected {
    background-color: #4a2220;
    border: 1px solid #f95f53;
}
QPushButton {
    min-width: 88px;
    min-height: 34px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
}
#secondaryButton {
    color: #d7d7d7;
    background-color: #353535;
    border: 1px solid #4a4a4a;
}
#secondaryButton:hover {
    background-color: #3d3d3d;
}
#primaryButton {
    color: white;
    background-color: #e6453a;
    border: 1px solid #ff776d;
}
#primaryButton:hover {
    background-color: #f6574b;
}
#primaryButton:disabled {
    color: #8a8a8a;
    background-color: #343434;
    border: 1px solid #434343;
}
#rememberCheck {
    color: #d0d0d0;
    font-size: 12px;
    padding-top: 4px;
}
#importHintBtn {
    color: #454545;
    font-size: 12px;
    font-weight: 400;
    border: none;
    border-radius: 0;
    min-width: 0;
    min-height: 0;
    background-color: transparent;
    text-align: center;
}
#importHintBtn:hover {
    color: #888888;
    background-color: #1e1e1e;
}
"""

LIST_CONTAINER_DRAG_STYLE = "#listContainer { background-color: #1a2620; border: 1px solid #5aaa88; border-radius: 8px; }"
