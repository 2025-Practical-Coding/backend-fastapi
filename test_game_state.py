from game_state import GameState
def main():
    # 1) 데이터 로드
    gs = GameState.load_from_file("Data.json")
    print(gs)  # 초기 상태

    # 2) 사용 가능한 지역 목록 출력
    regions = gs.listRegions()
    print("Regions:", regions)

    # 3) 첫 번째 지역 선택
    firstRegion = regions[0]
    assert gs.selectRegion(firstRegion), "지역 선택 실패"
    print("Selected region:", firstRegion)
    print(gs)  # region 필드 반영 확인

    # 4) 선택된 지역의 캐릭터 목록 출력
    chars = gs.listCharacters()
    print(f"Characters in {firstRegion}:", chars)

    # 5) 첫 캐릭터 slug로 5회 대화 반복
    slug = chars[0]
    for i in range(5):
        char = gs.talk(slug)
        print(f"Round {gs.currentRound-1}: talked with {char.slug}, affinity={char.affinity}, ally={char.isAlly}")

    # 6) 동료 리스트 확인
    print("Allies:", [c.slug for c in gs.allies])

    # 7) 라운드가 증가했는지, 게임 오버 여부 확인
    print(gs)  
    print("Game over?", gs.isGameOver())
    print("Result:", gs.result())

if __name__ == "__main__":
    main()
