# RustDesk 셀프 호스팅 원격지원 포털

고객은 웹페이지에서 **[실행파일 접속]** 버튼만 누르면 됩니다. 내려받은 프로그램을 실행하면
설치 없이 바로 **우리 회사 RustDesk 서버**로 연결되는 원격지원(Quick Support) 창이 뜹니다.
상담원은 그 창의 ID와 비밀번호로 접속합니다. 상담원은 RustDesk 앱을 쓰거나,
Guacamole을 통해 **브라우저만으로** 작업용 PC에 들어가 접속할 수 있습니다.

```
 고객 브라우저 ──https──▶ Caddy ─▶ portal (/, /download)
        │                       └▶ guacamole (/guacamole)  ◀── 상담원 브라우저
        ▼ 실행
 rustdesk-qs--<서버설정>.exe ──21115~21119──▶ hbbs / hbbr ◀── 상담원 RustDesk
                                                              (작업용 PC, RDP로 Guacamole에 연결)
```

## 동작 원리 (RustDesk 코드 수정 없음)

포털은 공식 `rustdesk.exe`를 그대로 내려주면서, 다운로드 파일 이름만 아래처럼 바꿔 줍니다.

```
rustdesk-qs--9JyNxETMyoTMuAjLw4y...Jye.exe
```

* `-qs-` 가 들어 있으면 RustDesk가 **Quick Support 모드**(설치 없이 실행)로 뜹니다
  (`src/core_main.rs` 의 `is_quick_support_exe`).
* `--` 뒤 토큰은 `{"host":…,"key":…,"relay":…}` JSON을 base64url로 인코딩한 뒤 거꾸로 뒤집은 값입니다.
  RustDesk가 실행될 때 이 이름을 해석해서 서버 주소와 공개키를 설정합니다(`src/custom_server.rs`).
  일반적으로 쓰는 `host=…,key=…` 방식은 공개키에 `/`가 들어 있으면 파일 이름이 깨집니다.
  이 방식은 그런 문제가 없습니다.
* 공개키는 hbbs가 처음 실행될 때 만드는 `data/id_ed25519.pub` 를 자동으로 읽습니다.

## 설치

필요한 것: 공인 IP(또는 포트포워딩)가 있는 Linux 서버, Docker, 도메인 1개.

```bash
cd support-portal
cp .env.example .env
```

`.env` 에서 `PORTAL_DOMAIN`, `RUSTDESK_HOST`, `COMPANY_NAME`, `SUPPORT_PHONE` 을 수정합니다.

```bash
docker compose up -d
```

방화벽/공유기에서 열어야 하는 포트:

| 포트 | 용도 |
|---|---|
| 80, 443 TCP | 웹 포털(HTTPS 인증서 자동 발급) |
| 21115–21117 TCP, 21116 UDP | RustDesk 서버(hbbs/hbbr) |
| 21118–21119 TCP | RustDesk 웹소켓(선택) |

`https://<도메인>/` 에 접속해 버튼을 눌러 보세요. 처음 실행할 때 `RUSTDESK_EXE_URL` 의 exe를
`files/rustdesk.exe` 로 한 번 내려받습니다. 직접 빌드한 exe나 코드서명된 exe를 쓰려면
그 파일을 같은 위치에 복사하면 됩니다(교체하면 바로 반영됩니다).

## 상담원 쪽

### A. RustDesk 앱 사용 (권장)
상담원 PC의 RustDesk에서 **설정 → 네트워크 → ID/릴레이 서버**에 `RUSTDESK_HOST` 값과
`data/id_ed25519.pub` 의 키를 입력합니다. 그다음 고객이 불러 준 ID와 비밀번호로 접속합니다.

### B. 브라우저만으로 사용 (Guacamole, reddit에서 제안된 방식)
여유 Windows PC(또는 VM) 한 대에 RustDesk를 설치하고 A처럼 서버를 설정합니다.
그 PC에서 원격 데스크톱(RDP)을 켜 둡니다.

1. `guacamole/user-mapping.xml` 에서 상담원 계정 비밀번호와 작업용 PC IP/계정을 수정합니다.
2. `docker compose --profile guacamole up -d`
3. 상담원은 어디서든 `https://<도메인>/guacamole/` 에 로그인합니다. 브라우저 안에 작업용 PC
   화면이 뜨면, 그 안의 RustDesk로 고객 ID에 접속합니다.

Kasm Workspaces를 써도 같은 방식으로 구성할 수 있습니다(브라우저 → 작업용 데스크톱 → RustDesk).

## 운영 시 참고

* **SmartScreen 경고**: 서명되지 않은 exe는 "Windows의 PC 보호" 창이 뜰 수 있습니다.
  코드서명 인증서로 서명한 exe를 `files/rustdesk.exe` 로 쓰면 경고가 줄어듭니다.
  파일 이름은 서명과 상관이 없어서 서명이 깨지지 않습니다.
* 고객이 같은 파일을 여러 번 받아 `(1)` 같은 접미사가 붙어도 정상적으로 인식됩니다.
* Quick Support 창을 닫으면 연결이 끝나고, PC에 아무것도 설치되어 남지 않습니다.
* 지금 지원하는 고객 PC는 Windows뿐입니다(파일 이름으로 설정하는 기능이 Windows 전용입니다).
* Guacamole 기본 비밀번호는 반드시 바꾸세요.

## 테스트

```bash
cd portal && python3 -m unittest -v test_server
```
