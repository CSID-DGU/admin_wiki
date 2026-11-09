# Pod별 독립 NFS client 도입

## 도입 근거

| 문서 | 결정 내용 |
| --- | --- |
| [261013 주간 리포트 C. Storage 서버 옵션 비교](https://app.notion.com/p/261013-3f7c7692a26380e3981ed4911deea86f#3f7c7692a26380649621cb498dd4fbec) | 모든 FARM 서버에 `async`, `nconnect=4` 옵션 결정 및 테스트 진행, 문제 없을 시 모든 LAB 서버에도 같은 옵션 적용 |
| [261103 주간 리포트 C. NFS 옵션 추가 실험](https://app.notion.com/p/261103-40cc7692a26380109d38d92c696994ab#40cc7692a263809995fcd3bc44a7e9a8) | 모든 LAB 서버 컨테이너, FARM 서버의 Pod별로 독립 NFS client 도입  |

## 구성


### Pod마다 마운트와 netns가 필요한 이유

리눅스 커널에서 NFS client는 네트워크 공간(netns)마다 따로 생긴다. 같은 netns에서 같은 NAS를 다시 마운트하면 새 client가 생기지 않고 기존 client를 같이 쓴다. 지금은 모든 Pod가 노드의 공용 마운트(`/home/tako<N>/share`)를 hostPath로 받기 때문에, 한 노드의 Pod 전부가 client 하나를 나눠 쓴다.

Pod마다 client를 따로 두려면 Pod마다 마운트를 하나씩 만들되, 각 마운트를 서로 다른 netns 안에서 실행해야 한다. 그래서 Pod마다 NFS 전용 netns를 하나 만들고, NAS 마운트를 그 안에서 실행한다.

```mermaid
---
config:
  flowchart:
    nodeSpacing: 70
---
flowchart LR
    subgraph node["FARM 노드 (물리 서버)"]
    %% pad: 바깥 상자 제목이 안쪽 상자에 가려지지 않도록 넣은 보이지 않는 상자
    subgraph pad[" "]
        subgraph podB["Pod B의 netns"]
            PB["Pod B<br/>사용자 프로그램"]
        end
        subgraph podA["Pod A의 netns"]
            PA["Pod A<br/>사용자 프로그램"]
        end
        subgraph nsB["Pod B 전용 NFS netns"]
            CB["NFS client<br/>veth IP 169.254.250.6"]
        end
        subgraph nsA["Pod A 전용 NFS netns"]
            CA["NFS client<br/>veth IP 169.254.250.2"]
        end
        subgraph hostns["노드 netns"]
            VB["노드 쪽 veth<br/>169.254.250.5"]
            VA["노드 쪽 veth<br/>169.254.250.1"]
            NIC["NAS 쪽 랜카드<br/>노드 IP"]
        end
    end
    end
    NAS["NAS<br/>100.100.100.120:2049"]

    PB -. "/home 읽기·쓰기<br/>(hostPath)" .-> CB
    PA -. "/home 읽기·쓰기<br/>(hostPath)" .-> CA
    CB -- "veth" --> VB
    CA -- "veth" --> VA
    VB --> NIC
    VA --> NIC
    NIC -- "출발 주소를 노드 IP로 변환(SNAT)" --> NAS

    style pad fill:none,stroke:none
```

### 구성 요소

| 구성 요소 | 하는 일 |
| --- | --- |
| NFS 전용 netns | Pod마다 하나씩 만드는 netns다. 여기서 NAS를 마운트하면 그 Pod만 쓰는 NFS client가 생긴다. Pod 자신은 이 netns에 속하지 않는다 |
| client 이름(identifier) | NAS가 client를 구분할 때 쓰는 이름이다. netns마다 다른 이름을 주며, 그 netns에서 처음 마운트하기 전에 정해야 한다 |
| veth | 두 netns를 잇는 가상 랜선이다. 한쪽 끝은 NFS 전용 netns에, 다른 쪽 끝은 노드 netns에 있다 |
| netns 안 라우팅 | NFS 전용 netns에서 NAS로 가는 패킷을 veth를 통해 노드로 보낸다. NAS 대역 말고 다른 경로는 두지 않는다 |
| SNAT | 노드가 패킷을 NAS로 내보낼 때 출발지 주소를 노드 IP로 바꾼다. 그래야 NAS가 응답을 노드로 돌려보낼 수 있다 |
| FORWARD 허용 | 노드가 veth와 랜카드 사이에서 패킷을 넘겨주도록 방화벽에서 허용한다. FORWARD 기본 정책이 DROP인 노드는 이 규칙이 없으면 패킷을 버린다 |
| rpc.gssd | Kerberos 인증을 맡는 프로그램이다. 커널이 인증을 요청하는 통로(rpc_pipefs)가 netns마다 따로 있으므로, NFS 전용 netns마다 하나씩 실행한다 |
| 마운트 | NFS 전용 netns의 네트워크를 써서 NAS를 마운트한다. 마운트된 폴더는 노드 파일시스템에 생긴다 |
| hostPath | 마운트된 폴더를 Pod의 `/home`으로 연결한다. `type: Directory`로 지정해서, 폴더가 없으면 Pod가 시작되지 않게 한다. 마운트 지점은 재부팅하면 비워지는 `/run` 아래에 있으므로, 재부팅 뒤 마운트 없이 빈 폴더가 `/home`으로 연결되는 일을 막을 수 있다 |

### veth로 노드와 잇는 이유

새로 만든 netns에는 네트워크 장치가 없다. farm7 시험 netns에서도 veth를 빼면 `lo`와 쓰지 않는 `tunl0`뿐이었다. NAS와 연결된 실제 랜카드(`eno1np0`)는 노드 netns에 있고, 랜카드 하나는 한 netns에만 속할 수 있어서 NFS 전용 netns로 옮겨 올 수 없다. 그래서 NFS 전용 netns의 패킷이 노드를 거쳐 NAS로 나가도록 다음과 같이 연결한다.

1. veth의 한쪽 끝은 NFS 전용 netns에, 다른 쪽 끝은 노드 netns에 둔다.
2. NFS 전용 netns에서 NAS로 보낸 패킷은 veth를 타고 노드로 넘어온다. 노드는 공유기처럼 이 패킷을 `eno1np0`으로 내보낸다.
3. 내보낼 때 출발지 주소를 노드 IP로 바꾼다(SNAT). NAS의 응답은 노드로 돌아오고, 노드가 다시 veth를 거쳐 NFS 전용 netns로 넘겨준다.

veth는 통신 경로일 뿐이고 마운트와는 관계없다. 마운트는 NFS 전용 netns에서 한 번만 한다.

Kubernetes Pod도 같은 방식으로 노드와 연결된다. Pod마다 자기 netns가 있고, veth로 노드와 이어진다. 노드에서 보이는 `cali...` 인터페이스가 이 veth의 노드 쪽 끝이다. NFS 전용 netns도 같은 방식으로 연결하되, 컨테이너 없이 NFS 통신만 한다는 점이 다르다.

### 노드는 패킷을 전달만 한다

패킷이 노드를 지나간다고 해서 노드의 NFS client를 쓰는 것은 아니다. 노드는 패킷을 넘겨주기만 하고, NAS와 NFS로 통신하는 것은 마운트를 실행한 netns의 client다. 2026-11-09 farm7에서 NAS(2049번 포트)로 열린 연결을 확인하면 아래처럼 두 연결이 따로 있다.

| 연결이 열린 곳 | 연결 | 쓰는 쪽 |
| --- | --- | --- |
| 노드 netns | `100.100.100.107:989 → 100.100.100.120:2049` | 기존 공용 마운트 `/home/tako7/share`. 다른 Pod들이 쓴다 |
| NFS 전용 netns | `169.254.250.2:891 → 100.100.100.120:2049`. 노드를 지날 때 출발지 주소가 `100.100.100.107`로 바뀐다 | csuhyeon Pod |

### 마운트 결과가 노드에서 보이는 이유

NFS 전용 netns에서 마운트할 때는 `nsenter --net`을 쓴다. 이 명령은 netns의 네트워크만 빌려 쓰고, 파일시스템(mount namespace)은 노드 것을 그대로 쓴다. 그래서 마운트된 폴더가 노드에 생기고, 노드에서 `findmnt`로 확인할 수 있다. Pod에 hostPath로 넘길 수 있는 것도 이 때문이다.

netns 안에서 명령을 실행할 때 흔히 쓰는 `ip netns exec`는 이 용도에 맞지 않는다. 이 명령은 netns에 들어가면서 mount namespace도 새로 만든다. 그래서 그 안에서 마운트하면 노드에서는 보이지 않고, Pod에 hostPath로 넘길 수도 없다.

## 연결 수와 슬롯

Pod마다 client를 두면 NAS로 가는 TCP 연결 수가 늘어난다. 또 client마다 응답을 기다리며 동시에 보내 둘 수 있는 요청 수(슬롯)도 정해야 한다.

### NAS 연결 상한

NAS 커널(sunrpc)은 새 TCP 연결이 들어올 때마다 연결 수를 확인한다. 연결 수가 아래 상한을 넘으면 커널 로그에 `too many open connections, consider increasing the number of threads`를 남기고, 가장 오래 쓰이지 않은 연결을 하나 끊는다.

```
연결 상한 = (NAS nfsd 스레드 수 + 3) × 20
```

nfsd 스레드 수는 NAS가 동시에 처리할 수 있는 요청 수다. NAS에서 `sudo cat /proc/fs/nfsd/threads`로 확인한다.

| 항목 | 값 |
| --- | --- |
| NAS nfsd 스레드 수 (2026-11-06 확인) | 122 |
| 연결 상한 | (122 + 3) × 20 = 2,500 |
| NAS 2049번 포트 연결 수 (2026-11-06 확인) | 22 |
| Pod별 client로 바꾼 뒤 예상 연결 수 | 약 200 (FARM 9대 × Pod 20개 + LAB) |

Pod별 client는 `nconnect=1`이라 client 하나가 연결 하나만 연다. 그래서 Pod가 늘어나도 연결 수는 상한의 10분의 1에 못 미친다. NAS에는 `ss`가 없으므로 연결 수는 `sudo netstat -tn | grep -c ':2049 '`로 센다.

### 슬롯 상한

슬롯은 client가 응답을 기다리면서 동시에 보내 둘 수 있는 요청 수다. TCP 연결마다 슬롯이 따로 있고, 요청을 보내면 슬롯 하나를 쓰고 응답을 받으면 돌려받는다. 리눅스는 처음에는 슬롯을 적게 잡고 요청이 몰릴수록 늘린다. 늘어날 수 있는 최대치가 `sunrpc.tcp_max_slot_table_entries`이고, 기본값 65536은 사실상 제한이 없는 값이다.

nconnect와 슬롯은 서로 다른 값이다. nconnect는 TCP 연결 수이고, 슬롯은 연결 하나에서 응답을 기다리는 요청 수다. 동시에 응답을 기다리는 요청의 총수는 연결 수 × 연결당 슬롯 수가 된다.

슬롯이 너무 많으면 `sec=krb5`에서 문제가 생긴다. `sec=krb5`에서는 요청마다 GSS 일련번호가 붙고, NAS는 지금까지 받은 가장 큰 번호에서 128 안쪽의 번호만 받는다. 그보다 오래된 번호의 요청은 오류 응답 없이 버린다. 응답을 기다리는 요청이 128개를 넘으면, NAS가 122개 스레드로 요청을 처리하는 순서가 조금만 어긋나도 일부 요청이 이 범위 밖으로 밀려난다. 버려진 요청을 기다리는 프로세스는 D 상태로 멈춘다.

2026-11-07 farm7에서 `nconnect=1`인 노드 공용 마운트로 대량 복사를 하던 중 WRITE 요청 4건이 응답 없이 멈췄다. 그때 이 마운트의 슬롯은 1,029개까지 늘어나 있었다. 원인은 위 범위 밖 폐기로 보고 있지만, NAS 쪽 증거로 확정하지는 못했다.

그래서 Pod별 client는 슬롯 상한을 64로 둔다. 2026-11-09 farm7에서 100GiB를 쓰고 읽어 비교한 결과는 다음과 같다.

| 슬롯 상한 | 쓰기 | 읽기 | 응답을 기다린 요청 수 최대 (20초 간격 측정) |
| --- | --- | --- | --- |
| 64 | 675MB/s | 698MB/s | 64 |
| 65536 (기본값) | 659MB/s | 670MB/s | 178 |

두 경우 모두 멈춘 요청은 없었다. 처리량이 거의 같으므로, 슬롯을 64로 묶어도 처리량 손실 없이 응답을 기다리는 요청을 128개 아래로 유지할 수 있다.

`sunrpc.tcp_max_slot_table_entries`는 netns마다 따로 있는 값이 아니라 노드 전체에 적용되는 값이고, 마운트할 때 TCP 연결을 만들면서 한 번 읽힌다. 그래서 NFS 전용 netns에서 마운트하기 직전에 값을 64로 바꾸고, 마운트가 끝나면 원래 값으로 되돌린다. 이미 만들어진 마운트에는 영향이 없다.
