# Kerberos/NFS

`kerberos-nfs`는 FARM/LAB 서버에서 Kerberos로 사용자를 인증하고 NFS 공유
스토리지의 파일 권한을 동일한 UID/GID 기준으로 적용하는 구성을 설명한다.

이 영역을 이해하려면 [설계](design.md)에서 Kerberos의 주요 개념, NFS 인증 흐름과
FARM/LAB 설정을 확인한다. 실제 설정 변경과 장애 대응은 [운영](operations.md),
과거 장애의 재현 조건과 분석 결과는 [디버깅 로그](debugging/index.md)에서
확인한다.

## 문서 구성

| 문서 | 내용 |
| --- | --- |
| 현재 페이지 | Kerberos/NFS 영역의 목적과 문서 구성 |
| [설계](design.md) | Kerberos 핵심 개념, NFS 인증 흐름, FARM/LAB 적용 설정과 선택 이유 |
| [운영](operations.md) | 계정과 credential 관리, mount 점검, KVNO·NFS 장애 대응 |
| [디버깅 로그](debugging/index.md) | 재현된 장애의 증상, 실험 조건, 증거와 복구 결과 |
