from time import sleep
from datetime import datetime
from typing import Optional
import requests
import json
import jsonpath
import os
import re
from http.cookiejar import LWPCookieJar
from requests.cookies import RequestsCookieJar

# 创建全局 Session 对象，统一管理 cookies 和 headers
session = requests.Session()

# 设置真实浏览器 User-Agent 和通用 headers
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Origin": "https://live.bilibili.com",
    }
)

COOKIE_JAR_PATH = os.path.join("cookie", "bilibili.cookies")


def load_cookies_from_file(cookie_path: str = COOKIE_JAR_PATH) -> bool:
    if not os.path.exists(cookie_path) or os.path.getsize(cookie_path) == 0:
        print(
            f"未找到 cookies 文件: {cookie_path}，请先运行 spider/get_cookie.py 扫码登录"
        )
        return False

    cookie_jar = LWPCookieJar(filename=cookie_path)
    try:
        cookie_jar.load(ignore_discard=True)
    except Exception as ex:
        print(f"读取 cookies 失败: {ex}")
        return False

    session_cookie_jar = RequestsCookieJar()
    session_cookie_jar.update(cookie_jar)
    session.cookies.update(session_cookie_jar)

    sessdata_values = [c.value for c in session.cookies if c.name == "SESSDATA"]
    if not sessdata_values:
        print("cookies 中未包含 SESSDATA，可能登录失败或已过期")
        return False
    if len(set(sessdata_values)) > 1:
        print("检测到多个 SESSDATA，已选择其中一个用于请求")

    return True


# 工具函数：清理文件/文件夹名，移除 Windows 非法字符
def sanitize_filename(name: str) -> str:
    if not isinstance(name, str):
        name = str(name or "")
    # 替换非法字符 \ / : * ? " < > |
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name)
    # 去除首尾的空格与点
    cleaned = cleaned.strip().strip(".")
    # 连续下划线归并
    cleaned = re.sub(r"_+", "_", cleaned)
    # 防止空字符串
    return cleaned or "unknown"


# 工具函数：在目录下生成不重名的文件名（若重名则追加数字后缀）
def ensure_unique_filename(directory: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = filename
    idx = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{base}_{idx}{ext}"
        idx += 1
    return candidate


def get_room_play_info(room_id: int) -> dict:
    kw = {
        "room_id": room_id,
        "qn": 10000,  # 请求最高画质
        "platform": "web",
        "protocol": "0,1",
        "format": "0,1,2",
        "codec": "0,1,2",
    }

    # 使用 session 发起请求，添加动态 Referer
    live = session.get(
        "https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo",
        params=kw,
        headers={"Referer": f"https://live.bilibili.com/{room_id}"},
        timeout=10,
    )

    result = live.json()
    # 检查返回状态
    if result.get("code") != 0:
        print(
            f"API 返回错误: code={result.get('code')}, message={result.get('message')}"
        )
        print("可能原因: SESSDATA 过期或未填写，或被风控")

    res1 = jsonpath.jsonpath(
        result,
        "$.data.playurl_info.playurl.stream[1].format[1].codec[1].url_info[0].host",
    )
    res2 = jsonpath.jsonpath(
        result, "$.data.playurl_info.playurl.stream[1].format[1].codec[1].base_url"
    )
    res3 = jsonpath.jsonpath(
        result,
        "$.data.playurl_info.playurl.stream[1].format[1].codec[1].url_info[0].extra",
    )
    res4 = jsonpath.jsonpath(
        result, "$.data.playurl_info.playurl.stream[1].format[1].codec[1].accept_qn"
    )

    # 打印可用的画质列表
    if res4 and res4[0]:
        print(f"可用画质列表 (qn): {res4[0]}")
        print(f"最高画质值: {max(res4[0])}")

    return {
        "site": res1[0] if res1 else "",
        "base_url": res2[0] if res2 else "",
        "extra": res3[0] if res3 else "",
        "qn": res4[0] if res4 else [],
        "full_url": "".join([res1[0], res2[0], res3[0]]) if (res1 and res2 and res3) else "",
    }


def get_m3u8_params(url: str) -> dict:
    live = session.get(url, timeout=10)
    lines = live.text.splitlines()
    segments = []
    header_file = None

    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-MAP:URI="):
            header_file = line.split('"')[1]
        elif line.startswith("#EXTINF"):
            duration = line.split(":")[1].split(",")[0]
            file_name = lines[i + 1]
            segments.append({"duration": float(duration), "file_name": file_name})
    print("---- M3U8 参数解析结果: ----")
    print(f"Header file: {header_file}")
    print(segments)
    return {"header_file": header_file, "segments": segments}


def download_header(
    site: str,
    base_url: str,
    extra: str,
    headerFile: str,
    room_id: int,
    maxQn: int,
) -> Optional[bytes]:
    # 替换 extra 中的 qn 参数为 maxQn 的值
    extra = re.sub(r"qn=\d+", f"qn={maxQn}", extra)

    if not headerFile:
        return None

    header_path = base_url.rsplit("/", 1)[0] + "/" + headerFile
    url = site + header_path + "?" + extra
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        print(f"Downloaded header file (memory): {headerFile}")
        return response.content
    except Exception as ex:
        print(f"Warning: 下载头文件失败 {headerFile}: {ex}")
        return None


from typing import Optional

def download_segment(
    site: str,
    base_url: str,
    extra: str,
    segment: dict,
    room_id: int,
    maxQn: int,
    output_file: Optional[str] = None,
    header_bytes: Optional[bytes] = None,
):
    # 创建目录结构 temp/room_id
    temp_dir = os.path.join("temp", str(room_id))
    os.makedirs(temp_dir, exist_ok=True)

    # 替换 extra 中的 qn 参数为 maxQn 的值
    extra = re.sub(r"qn=\d+", f"qn={maxQn}", extra)

    base_path = base_url.rsplit("/", 1)[0]
    url = site + base_path + "/" + segment["file_name"] + "?" + extra
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        segment_file_path = os.path.join(temp_dir, segment["file_name"])
        with open(segment_file_path, "wb") as f:
            f.write(response.content)
        print(f"Downloaded segment: {segment_file_path}")

        # 实时拼接：下载完成后立即追加到输出文件
        if output_file:
            append_segment_to_file(
                segment_file_path,
                output_file,
                header_bytes=header_bytes,
                room_id=room_id,
            )

    except Exception as ex:
        print(f"Warning: 下载片段失败 {segment['file_name']}: {ex}")


def append_segment_to_file(
    segment_file: str,
    output_file: str,
    header_file: Optional[str] = None,
    header_bytes: Optional[bytes] = None,
    room_id: Optional[int] = None,
):
    """实时追加片段到输出文件"""
    mode = (
        "wb" if not os.path.exists(output_file) else "ab"
    )  # 首次写入用 wb，后续追加用 ab

    with open(output_file, mode) as outfile:
        # 如果是第一次写入且有头文件，先写入头文件
        if mode == "wb" and header_file and room_id:
            temp_dir = os.path.join("temp", str(room_id))
            header_file_path = os.path.join(temp_dir, header_file)
            if os.path.exists(header_file_path):
                with open(header_file_path, "rb") as infile:
                    outfile.write(infile.read())
                print(f"[实时拼接] 写入头文件: {header_file}")
            os.remove(header_file_path)  # 写入后删除头文件
        elif mode == "wb" and header_bytes:
            outfile.write(header_bytes)
            print("[实时拼接] 写入头文件: memory")

        # 写入片段
        if os.path.exists(segment_file):
            with open(segment_file, "rb") as infile:
                outfile.write(infile.read())
            print(
                f"[实时拼接] 追加片段: {os.path.basename(segment_file)} -> {output_file}"
            )
            # 删除临时片段文件
            os.remove(segment_file)


def download_live(
    urls: dict,
    size_MB: int = 20,
    filename: str = "live_video.mp4",
    room_id: int = 0,
    uname: str = "",
):
    # 使用可用的最高画质
    max_qn = max(urls["qn"]) if urls["qn"] else 10000
    full_url = urls.get("full_url", "")

    if not full_url:
        print("无效的直播 URL")
        return

    segments = get_m3u8_params(urls["full_url"])

    # 下载头文件
    header_bytes = download_header(
        urls["site"],
        urls["base_url"],
        urls["extra"],
        segments["header_file"],
        room_id,
        max_qn,
    )

    # 生成用户名目录并确保文件名不重名
    safe_uname = sanitize_filename(uname) if uname else "unknown_user"
    output_dir = os.path.join("downloads",safe_uname)
    os.makedirs(output_dir, exist_ok=True)

    # 清理传入的文件名并生成唯一路径
    base_name, ext = os.path.splitext(filename)
    safe_base = sanitize_filename(base_name)
    ext = ext or ".flv"
    def build_output_path(part_index: int) -> str:
        part_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        desired_name = f"{safe_base}_{part_time}{ext}"
        unique_name = ensure_unique_filename(output_dir, desired_name)
        return os.path.join(output_dir, unique_name)

    start_index = 0
    target_size_bytes = size_MB * 1024 * 1024  # 转换为字节
    part_index = 1
    output_path = build_output_path(part_index)
    temp_dir = os.path.join("temp", str(room_id))

    # 去除 .m4s 后缀并转换为数字，保存到 segment["file_number"]
    file_name = segments["segments"][0].get("file_name", "")
    if file_name.endswith(".m4s"):
        try:
            start_index = int(file_name[:-4])
        except ValueError:
            nums = re.findall(r"\d+", file_name)
            start_index = int(nums[0]) if nums else 0

    print(f"\n开始实时下载并拼接到文件: {output_path}")
    print(f"使用画质: {max_qn}")
    print(f"每个分片最大大小: {size_MB} MB\n")

    while True:
        # 检查当前文件大小
        current_size = (
            os.path.getsize(output_path) if os.path.exists(output_path) else 0
        )
        current_size_mb = current_size / (1024 * 1024)

        if current_size >= target_size_bytes:
            print(
                f"\n分片完成: {output_path} (当前: {current_size_mb:.2f} MB)"
            )
            part_index += 1
            output_path = build_output_path(part_index)
            print(f"开始新分片: {output_path}")
            continue

        download_segment(
            urls["site"],
            urls["base_url"],
            urls["extra"],
            {
                "file_name": f"{start_index}.m4s",
                "duration": segments["segments"][0].get("duration", 0),
            },
            room_id,
            max_qn,
            output_file=output_path,  # 传递输出文件路径
            header_bytes=header_bytes,  # 传递头文件内容
        )

        # 显示进度
        new_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        new_size_mb = new_size / (1024 * 1024)
        progress = min((new_size / target_size_bytes) * 100, 100.0)
        print(
            f"[进度] 分片{part_index:03d} "
            f"{new_size_mb:.2f}/{size_MB} MB ({progress:.1f}%)"
        )

        start_index += 1
        segments = get_m3u8_params(urls["full_url"])
        if not segments["segments"]:
            print("未获取到新的片段，可能直播已结束")
            break
        elif f"{start_index}.m4s" not in [
            seg["file_name"] for seg in segments["segments"]
        ] and start_index > int(segments["segments"][0].get("file_name", "")[:-4]):
            print("当前片段尚未生成，等待中...")
            sleep(3)
            continue

    final_size_mb = (
        os.path.getsize(output_path) / (1024 * 1024)
        if os.path.exists(output_path)
        else 0
    )
    print(f"\n实时拼接完成！最后分片: {output_path}")
    print(f"最终大小: {final_size_mb:.2f} MB")

    if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
        os.rmdir(temp_dir)


def get_uid_live_id(uid: str) -> Optional[dict]:
    """根据 UID 获取直播间 ID"""
    url = f"https://api.live.bilibili.com/live_user/v1/Master/info?uid={uid}"
    try:
        response = session.get(
            url, timeout=10, headers={"Referer": "https://live.bilibili.com/"}
        )
        response.raise_for_status()

        try:
            data = response.json()
        except Exception as ex:
            preview = response.text[:300]
            encoding = response.headers.get("Content-Encoding", "")
            ctype = response.headers.get("Content-Type", "")
            print(f"UID 接口返回非 JSON: {ex}; 状态码={response.status_code}")
            print(f"Content-Encoding: {encoding}; Content-Type: {ctype}")
            print(f"响应预览: {preview}")
            return None

        print(data)

        if data.get("code") == 0:
            d = data.get("data", {})
            # 兼容不同接口字段：可能是 roomid/liveStatus 或 room_id/live_status
            room_id = d.get("roomid") or d.get("room_id")
            live_status = d.get("liveStatus") or d.get("live_status")

            # 输出更清晰的诊断信息
            print(
                f"HTTP: {response.status_code}, API code: {data.get('code')} (0 表示业务成功)"
            )
            print(f"用户 {uid} 的直播间 ID: {room_id}")
            if live_status is not None:
                print(f"直播状态: {'直播中' if int(live_status) == 1 else '未开播'}")
            return d
        else:
            print(
                f"API 返回错误: code={data.get('code')}, message={data.get('message')}"
            )
            return None
    except Exception as ex:
        print(f"获取直播间 ID 失败: {ex}")
        return None


def get_live_status(room_id: int) -> Optional[dict]:
    """检查直播间是否在直播中"""
    url = f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}"
    try:
        response = session.get(
            url, timeout=10, headers={"Referer": "https://live.bilibili.com/"}
        )
        response.raise_for_status()

        data = response.json()

        if data.get("code") == 0:
            live_status = data["data"]["live_status"]
            live_title = data["data"]["title"]
            status_str = (
                "直播中"
                if live_status == 1
                else ("轮播中" if live_status == 2 else "未开播")
            )
            print(f"直播间 {room_id} 直播状态: {status_str}")
            print(f"直播标题: {live_title}")
            return data["data"]
        else:
            print(
                f"API 返回错误: code={data.get('code')}, message={data.get('message')}"
            )
            return None
    except Exception as ex:
        print(f"获取直播状态失败: {ex}")
        return None


if __name__ == "__main__":
    if not load_cookies_from_file():
        print("缺少有效 cookies，退出。")
        exit(1)

    user_info = get_uid_live_id("474595627")
    if not user_info:
        print("获取用户信息失败，可能接口返回错误或 SESSDATA 无效。")
        exit(1)

    room_id = user_info.get("roomid") or user_info.get("room_id")
    if not room_id:
        print(f"未找到 room_id，返回数据: {user_info}")
        exit(1)
    try:
        room_id = int(room_id)
    except Exception:
        print(f"room_id 无效: {room_id}")
        exit(1)

    info = user_info.get("info") or {}
    uname = info.get("uname") if isinstance(info, dict) else None
    uname = uname or user_info.get("uname") or "unknown_user"

    live_status = get_live_status(room_id)
    if not live_status:
        print("无法获取直播状态，退出")
        exit(1)

    if int(live_status.get("live_status", 0)) in (1, 2):
        urls = get_room_play_info(room_id)
        if not urls.get("full_url"):
            print("未获取到播放地址，退出")
            exit(1)

        title_safe = sanitize_filename(live_status.get("title", "unknown"))
        live_time = live_status.get("live_time", "")
        filename = f"{title_safe}-{live_time}.flv"
        download_live(
            urls,
            size_MB=20,
            filename=filename,
            room_id=room_id,
            uname=uname,
        )
    else:
        print("直播未开播或不在直播状态")
