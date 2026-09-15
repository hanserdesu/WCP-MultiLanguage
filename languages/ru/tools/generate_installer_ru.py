# -*- coding: utf-8 -*-
"""基于 French 安装器生成俄语一键安装脚本 Install-WCP-Russian.ps1"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_ROOT = ROOT.parent
FR_PS1 = INTEGRATION_ROOT / "French" / "installer" / "Install-WCP-French.ps1"
RU_PS1 = ROOT / "installer" / "Install-WCP-Russian.ps1"

def main():
    text = FR_PS1.read_text(encoding='utf-8')
    
    # 替换名称
    text = text.replace("WcpFrenchZipSession", "WcpRussianZipSession")
    text = text.replace("French", "Russian")
    text = text.replace("french", "russian")
    text = text.replace("法语", "俄语")
    text = text.replace("FrWordListMod", "RuWordListMod")
    text = text.replace("SentenceAudioFrMod", "SentenceAudioRuMod")
    text = text.replace("fr_word_audio", "ru_word_audio")
    text = text.replace("fr_db_payload", "ru_db_payload")
    text = text.replace("catbar_french_book.json", "catbar_russian_book.json")
    text = text.replace("wcp_french.db", "wcp_russian.db")
    
    # 目标槽位改为 3
    text = text.replace("int targetSlot = 2;", "int targetSlot = 3;")
    text = text.replace("$targetSlot = 2", "$targetSlot = 3")
    text = text.replace("targetSlot = 2", "targetSlot = 3")
    
    # 指纹替换
    text = text.replace(
        "376af2eae0292052cefb4cb0d673f48a5ca480a38e25a6bf5353998caea17e9d",
        "dfecb0ab75e9b3ef75aedd47c677d68594b060bfbb84cc6bd94efd7888f4b74e"
    )
    text = text.replace("8116", "8451")

    RU_PS1.write_text(text, encoding='utf-8')
    print("Generated", RU_PS1, "bytes:", len(text))

if __name__ == '__main__':
    main()
