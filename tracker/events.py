"""官方行事曆事件的中文名稱。"""
from __future__ import annotations

import re


# 官方行事曆常見名稱的中文對照（找不到就保留英文）
EVENT_ZH = [
    (r"FIRST Robotics Competition Kickoff", "FRC Kickoff（公布比賽與手冊）"),
    (r"Official Q&A Opens", "官方 Q&A 開放提問"),
    (r"Official Q&A Closes", "官方 Q&A 關閉"),
    (r"Events Registration Closes", "賽事報名截止"),
    (r"Kit and Kickoff Registration Closes", "Kit 與 Kickoff 報名截止"),
    (r"Drive Base & Black Tote Opt Out Closes", "底盤／Black Tote 退訂截止"),
    (r"Payment Due - FIRST Robotics Competition Initial Event", "首場賽事報名費繳費截止"),
    (r"Payment Due - FIRST Robotics Competition Additional", "加報賽事繳費截止"),
    (r"Payment Due - FIRST Robotics Competition Championship", "世界賽報名費繳費截止"),
    (r"Pre-Kickoff Virtual Kit Release", "Kickoff 前虛擬 Kit 公布"),
    (r"Virtual Kit Kickoff Release", "Kickoff 虛擬 Kit 公布"),
    (r"Kickoff Kit Replacement Parts System Opens", "Kickoff Kit 缺件補發開放"),
    (r"Kickoff Kit Replacement Parts System Closes", "Kickoff Kit 缺件補發截止"),
    (r"FIRST Choice: Priority Lists Opens", "FIRST Choice 優先清單開放"),
    (r"FIRST Choice: Priority Lists Closes", "FIRST Choice 優先清單截止"),
    (r"FIRST Choice Regular Ordering Opens", "FIRST Choice 一般訂購開放"),
    (r"FIRST Choice Closes", "FIRST Choice 關閉"),
    (r"Digital Animation Award Closes", "Digital Animation Award 截止"),
    (r"FIRST Impact Award Application Closes", "FIRST Impact Award 申請截止"),
    (r"^Week Zero$", "Week 0 熱身賽"),
    (r"^Week (\d) Competition Events$", r"第 \1 週賽事"),
    (r"^FIRST Championship$", "FIRST 世界賽"),
]


def event_zh(label: str) -> str:
    for pat, zh in EVENT_ZH:
        if re.search(pat, label):
            return re.sub(pat, zh, label) if "\\" in zh else zh
    return ""
