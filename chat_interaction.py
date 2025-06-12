import os
import re
import json
import random
from openai import OpenAI
from dotenv import load_dotenv
from game_state import GameState, Character

# 환경변수에서 OpenAI 키 로드 및 클라이언트 초기화
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def getPrompt(gs: GameState, character: Character, userInput: str) -> list[dict]:
    """
    LLM에게 보낼 메시지 리스트 생성
    - system: 현재 지역과 캐릭터 배경 기반 오프닝 + 캐릭터 역할 지시
    - user: 실제 유저 입력
    """
    region = character.region  # character에 포함된 region 사용
    story = character.story.replace("\n", " ").strip()
    firstSentence = story.split(".")[0]

    if len(firstSentence) > 100:
        firstSentence = firstSentence[:100] + "..."

    opening = (
        f"{region} 지역에서 {character.name}({character.subtitle})과 마주쳤습니다. "
        f"{firstSentence}. 대화를 시작하세요."
    )
    curConv = gs.convCounts.get(character.slug, 0) + 1
    isOver = curConv >= gs.convLimit
    systemMsg = (
        opening + "\n\n"
        f"당신은 게임 캐릭터 {character.name}({character.subtitle})입니다.\n"
        f"스토리: {character.story}\n\n"
        "유저와 자신의 스토리에 맞춰 몰입하여 대화하세요.\n"
        f"{character.affinity}가 유저에 대한 당신의 호감도 입니다.\n"
        "호감도가 높다면 함께하는 것에 고민하고, 낮다면 함께하지 않겠다고고 대응하세요.\n"
        "긍정적이라도 함께하겠다는 확답은 절대로 하면 안됩니다.\n"
        "아래 **반드시** JSON 코드블록(Triple backticks)으로만 응답하세요:\n"
        "```json\n"
        "{\n"
        "  \"reply\": \"<대화 내용>\",\n"
        "  \"delta\": <호감도 변화량: 정수>,\n"
        "  \"narration\": \"<호감도 변화와 상황 설명 텍스트>\"\n"
        "}```\n"
        "delta 값은 -10에서 10사이의 정수, narration은 delta에 따른 서사적 설명을 포함하세요.\n"
    )
    return [
        {"role": "system", "content": systemMsg},
        {"role": "user",   "content": userInput}
    ]

def sayGoodBye(gs: GameState, character: Character) -> dict:
    region = character.region
    if character.affinity >= gs.affinityThreshold:
        systemMsg = (
            f"당신은 게임 캐릭터 {character.name}({character.subtitle})입니다.\n"
            f"스토리: {character.story}\n\n"
            "당신은 이제 유저와 대화를 마무리하려 합니다.\n"
            "반드시 유저가 가는 길에 함께 하겠다는 응답을 스토리를 기반으로 구성하세요.\n"
            "아래 **반드시** JSON 코드블록(Triple backticks)으로만 응답하세요:\n"
            "```json\n"
            "{\n"
            "  \"reply\": \"<대화 내용>\",\n"
            "  \"narration\": \"<상황 설명 텍스트>\"\n"
            "}```\n"
        )
    else:
        systemMsg = (
            f"당신은 게임 캐릭터 {character.name}({character.subtitle})입니다.\n"
            f"스토리: {character.story}\n\n"
            "당신은 이제 유저와 대화를 마무리하려 합니다.\n"
            "유저가 가는 길에 함께하지 않않겠다는 응답을 스토리를 기반으로 구성하세요.\n"
            "아래 **반드시** JSON 코드블록(Triple backticks)으로만 응답하세요:\n"
            "```json\n"
            "{\n"
            "  \"reply\": \"<대화 내용>\",\n"
            "  \"narration\": \"<상황 설명 텍스트>\"\n"
            "}```\n"
        )

    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": systemMsg}
        ],
        max_tokens=350
    )
    text = resp.choices[0].message.content.strip()

    match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if match:
        jsonStr = match.group(1)
    else:
        fallback = re.search(r'\{[\s\S]*\}', text)
        if fallback:
            jsonStr = fallback.group(0)
        else:
            print("json parsing error")
            return {
                "region": region,
                "character": {"slug": character.slug, "name": character.name, "subtitle": character.subtitle},
                "reply": text,
                "narration": "",
                "totalAffinity": character.affinity,
                "convCount": gs.convCounts.get(character.slug, 0),
                "convLimit": gs.convLimit,
                "allies": [
                    {"slug": c.slug, "name": c.name, "subtitle": c.subtitle}
                    for c in gs.allies
                ]
            }
    data = json.loads(jsonStr)
    return {
        "region": region,
        "character": {"slug": character.slug, "name": character.name, "subtitle": character.subtitle},
        "reply": data.get("reply", ""),
        "narration": data.get("narration", ""),
        "totalAffinity": character.affinity,
        "convCount": gs.convCounts.get(character.slug, 0),
        "convLimit": gs.convLimit,
        "allies": [
            {"slug": c.slug, "name": c.name, "subtitle": c.subtitle}
            for c in gs.allies
        ]
    }

def chatWithCharacter(gs: GameState, slug: str, name: str, userInput: str) -> dict:
    character = next(
        (c for region in gs.regions for c in region.characters if c.slug == slug),
        None
    )
    if not character:
        raise ValueError(f"Unknown character slug: {slug}")

    gs.currentCharacter = character

    messages = getPrompt(gs, character, userInput)
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=350
        )
    except Exception as e:
        print("[ERROR] OpenAI 응답 생성 실패:", e)
        raise

    text = resp.choices[0].message.content.strip()
    print("[DEBUG] LLM 응답 원문:", text)

    match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if match:
        json_str = match.group(1)
        print("[DEBUG] JSON 코드블럭 추출 성공")
    else:
        fallback = re.search(r'\{[\s\S]*\}', text)
        if fallback:
            json_str = fallback.group(0)
            print("[WARN] 백업 JSON 추출 성공")
        else:
            print("[ERROR] JSON 파싱 실패")

    if match:
        jsonStr = match.group(1)
    else:
        fallback = re.search(r'\{[\s\S]*\}', text)
        if fallback:
            jsonStr = fallback.group(0)
        else:
            print("json parsing error")
            return {
                "region": character.region,
                "character": {"slug": character.slug, "name": character.name, "subtitle": character.subtitle, "isAlly": character.isAlly},
                "userInput": userInput,
                "reply": text,
                "delta": 0,
                "narration": "",
                "totalAffinity": character.affinity,
                "convCount": gs.convCounts.get(slug, 0),
                "convLimit": gs.convLimit,
                "allies": [
                    {"slug": c.slug, "name": c.name, "subtitle": c.subtitle}
                    for c in gs.allies
                ]
            }

    data = json.loads(jsonStr)
    print("[DEBUG] JSON 로드 성공:", data)  # ✅ 여기에 추가
    print("[DEBUG] delta 값:", data.get("delta", 0))  # ✅ 여기에 추가

    try:
        delta = int(data.get("delta", 0))
    except Exception as e:
        print("[ERROR] delta 변환 실패:", e)
        delta = 0

    print(f"[DEBUG] talk() 호출 전: affinity={character.affinity}, count={gs.convCounts.get(slug, 0)}")  # ✅ 추가
    gs.talk(slug, name, affinityChange=delta)
    print(f"[DEBUG] talk() 호출 후: affinity={character.affinity}, count={gs.convCounts.get(slug, 0)}")  # ✅ 추가
    
    return {
        "region": character.region,
        "character": {
            "slug": character.slug,
            "name": character.name,
            "subtitle": character.subtitle,
            "isAlly": character.isAlly
        },
        "userInput": userInput,
        "reply": data.get("reply", ""),
        "delta": delta,
        "narration": data.get("narration", ""),
        "totalAffinity": character.affinity,
        "convCount": gs.convCounts.get(slug, 0),
        "convLimit": gs.convLimit,
        "allies": [
            {
                "slug": c.slug,
                "name": c.name,
                "subtitle": c.subtitle
            }
            for c in gs.allies
        ]
    }

def getOpening(gs: GameState, character: Character) -> str:
    region = character.region
    story = character.story.replace("\n", " ").strip()
    firstSentence = story.split(".")[0][:100]
    if len(firstSentence) > 100:
        firstSentence = firstSentence[:100] + "..."
    return f"{region} 지역에서 {character.name}({character.subtitle})과(와) 마주쳤습니다. {firstSentence}."

def ending(gs: GameState):
    if len(gs.allies) < gs.allyThreshold:
        resultText = "Fail"
        msg = (
            "당신은 리그 오브 레전드 세계관에 정통한 내러티브 작가입니다.\n"
            "한 유저가 동료를 영입해 바론을 잡으려 했지만 충분한 수의 동료를 영입하지 못한 유저는 바론을 잡는 것에 실패했습니다.\n"
            f"현재 동료의 수는 {len(gs.allies)}입니다.\n"
            "아래 **반드시** JSON 코드블록(Triple backticks)으로만 응답하세요:\n"
            "```json\n"
            "{\n"
            "  \"narration\": \"<게임 결과 설명 텍스트>\",\n"
            "  \"result\": \"Fail\"\n"
            "}```\n"
        )
    elif gs.totalRelationship < gs.relationshipThreshold:
        resultText = "Fail"
        msg = (
            "당신은 리그 오브 레전드 세계관에 정통한 내러티브 작가입니다.\n"
            "충분한 수의 동료를 영입했지만 몇몇 동료들의 연계가 좋지않아 잡는 것에 실패했습니다.\n"
            f"최종 동료들 간의 관계 수치는 {gs.totalRelationship}입니다.\n"
            "아래 **반드시** JSON 코드블록(Triple backticks)으로만 응답하세요:\n"
            "```json\n"
            "{\n"
            "  \"narration\": \"<게임 결과 설명 텍스트>\",\n"
            "  \"result\": \"Fail\"\n"
            "}```\n"
        )
    else:
        resultText = "Success"
        msg = (
            "당신은 리그 오브 레전드 세계관에 정통한 내러티브 작가입니다.\n"
            "동료들의 연계가 훌륭하여 드디어 바론을 잡는 것에 성공했습니다.\n"
            "아래 **반드시** JSON 코드블록(Triple backticks)으로만 응답하세요:\n"
            "```json\n"
            "{\n"
            "  \"narration\": \"<게임 결과 설명 텍스트>\",\n"
            "  \"result\": \"Success\"\n"
            "}```\n"
        )

    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": msg}],
        max_tokens=350
    )
    text = resp.choices[0].message.content.strip()

    match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if match:
        jsonStr = match.group(1)
    else:
        fallback = re.search(r'\{[\s\S]*\}', text)
        if fallback:
            jsonStr = fallback.group(0)
        else:
            print("json parsing error")
            return {
                "gameOver": True,
                "narration": "",
                "result": resultText,
                "relationship": gs.totalRelationship,
                "allies": len(gs.allies)
            }

    data = json.loads(jsonStr)
    return {
        "gameOver": True,
        "narration": data.get("narration", ""),
        "result": data.get("result", resultText),
        "relationship": gs.totalRelationship,
        "allies": len(gs.allies)
    }
