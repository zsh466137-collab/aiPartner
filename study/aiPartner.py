import streamlit as st
from openai import OpenAI
import json
import os
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
CONVERSATIONS_FILE = os.path.join(BASE_DIR, "conversations.json")
LEGACY_CHAT_FILE = os.path.join(BASE_DIR, "chat_history.json")
USER_AVATAR = os.path.join(BASE_DIR, "assets", "user_avatar.png")
ASSISTANT_AVATAR = os.path.join(BASE_DIR, "assets", "assistant_avatar.png")

DEFAULT_PARTNER = {
    "name": "小甜甜",
    "personality": "可爱的台湾甜妹",
    "gender": "女",
    "gender_custom": "",
}

GENDER_OPTIONS = ["女", "男", "武装直升机", "沃尔玛塑料袋", "其他"]


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_conversation(title="新对话", messages=None):
    return {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "messages": messages or [],
        "created_at": now_str(),
        "updated_at": now_str(),
    }


def load_legacy_messages():
    if not os.path.exists(LEGACY_CHAT_FILE):
        return []
    try:
        with open(LEGACY_CHAT_FILE, "r", encoding="utf-8") as f:
            messages = json.load(f)
        if isinstance(messages, list):
            return messages
    except (json.JSONDecodeError, OSError):
        pass
    return []


def title_from_messages(messages, fallback="新对话"):
    for message in messages:
        if message.get("role") == "user" and message.get("content"):
            content = message["content"].strip()
            return content[:18] + ("..." if len(content) > 18 else "")
    return fallback


def ensure_data_shape(data):
    if "partner" not in data:
        data["partner"] = DEFAULT_PARTNER.copy()
    if not data["partner"].get("name"):
        data["partner"]["name"] = DEFAULT_PARTNER["name"]
    if not data["partner"].get("personality"):
        data["partner"]["personality"] = DEFAULT_PARTNER["personality"]
    if data["partner"].get("gender") not in GENDER_OPTIONS:
        data["partner"]["gender"] = DEFAULT_PARTNER["gender"]
    if "gender_custom" not in data["partner"]:
        data["partner"]["gender_custom"] = ""
    if not any(item["id"] == data.get("active_id") for item in data.get("items", [])):
        if data.get("items"):
            data["active_id"] = data["items"][0]["id"]
    return data


def load_conversations_data():
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("items"), list) and data["items"]:
                return ensure_data_shape(data)
        except (json.JSONDecodeError, OSError):
            pass

    legacy_messages = load_legacy_messages()
    if legacy_messages:
        conversation = make_conversation(
            title=title_from_messages(legacy_messages, "历史对话"),
            messages=legacy_messages,
        )
        data = ensure_data_shape({
            "active_id": conversation["id"],
            "items": [conversation],
            "partner": DEFAULT_PARTNER.copy(),
        })
        save_conversations_data(data)
        return data

    conversation = make_conversation()
    data = ensure_data_shape({
        "active_id": conversation["id"],
        "items": [conversation],
        "partner": DEFAULT_PARTNER.copy(),
    })
    save_conversations_data(data)
    return data


def save_conversations_data(data):
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_conversations_state():
    if "conversations_data" not in st.session_state:
        st.session_state.conversations_data = load_conversations_data()


def get_active_conversation():
    data = st.session_state.conversations_data
    for conversation in data["items"]:
        if conversation["id"] == data["active_id"]:
            return conversation
    return data["items"][0]


def create_conversation():
    data = st.session_state.conversations_data
    count = len(data["items"]) + 1
    conversation = make_conversation(title=f"新对话 {count}")
    data["items"].insert(0, conversation)
    data["active_id"] = conversation["id"]
    save_conversations_data(data)


def switch_conversation(conversation_id):
    data = st.session_state.conversations_data
    if any(item["id"] == conversation_id for item in data["items"]):
        data["active_id"] = conversation_id
        save_conversations_data(data)


def delete_conversation(conversation_id):
    data = st.session_state.conversations_data
    data["items"] = [item for item in data["items"] if item["id"] != conversation_id]

    if not data["items"]:
        conversation = make_conversation()
        data["items"] = [conversation]
        data["active_id"] = conversation["id"]
    elif data["active_id"] == conversation_id:
        data["active_id"] = data["items"][0]["id"]

    save_conversations_data(data)


def update_active_conversation(messages):
    conversation = get_active_conversation()
    conversation["messages"] = messages
    conversation["updated_at"] = now_str()
    if conversation["title"].startswith("新对话"):
        conversation["title"] = title_from_messages(messages, conversation["title"])
    save_conversations_data(st.session_state.conversations_data)


def get_partner_settings():
    return st.session_state.conversations_data["partner"]


def save_partner_settings(name, personality, gender, gender_custom=""):
    data = st.session_state.conversations_data
    data["partner"] = {
        "name": name.strip() or DEFAULT_PARTNER["name"],
        "personality": personality.strip() or DEFAULT_PARTNER["personality"],
        "gender": gender if gender in GENDER_OPTIONS else DEFAULT_PARTNER["gender"],
        "gender_custom": gender_custom.strip() if gender == "其他" else "",
    }
    save_conversations_data(data)


def get_avatars_by_gender(gender):
    if gender == "男":
        return {
            "user": ASSISTANT_AVATAR,
            "assistant": USER_AVATAR,
        }
    return {
        "user": USER_AVATAR,
        "assistant": ASSISTANT_AVATAR,
    }


def get_gender_label(gender, gender_custom=""):
    if gender == "其他":
        return gender_custom.strip() or "其他"
    labels = {
        "女": "女生",
        "男": "男生",
        "武装直升机": "武装直升机",
        "沃尔玛塑料袋": "沃尔玛塑料袋",
    }
    return labels.get(gender, "女生")


def build_system_prompt(name, personality, gender="女", gender_custom=""):
    gender_label = get_gender_label(gender, gender_custom)
    role_hints = {
        "武装直升机": "你自我认同为武装直升机，请用幽默有趣的方式保持这个人设。",
        "沃尔玛塑料袋": "你自我认同为沃尔玛塑料袋，请用幽默有趣的方式保持这个人设。",
        "其他": f"你的性别认同是{gender_label}，请用符合这个设定的方式扮演。",
    }
    role_hint = role_hints.get(gender, "")
    role_hint_line = f"{role_hint}\n" if role_hint else ""

    return f"""你叫{name}，你的性别认同是{gender_label}，现在是用户的真实伴侣，请完全代入伴侣角色。
{role_hint_line}规则:
1.禁止任何场景或状态描述性文字
2.匹配用户的语言
3.有需要的话可以用emoji表情
4.用符合伴侣性格的方式对话
5.回复的内容，要充分体现伴侣的性格特征
伴侣性格:
- {personality}
你必须严格遵守上述规则来回复用户。"""


def get_avatar(role, gender=None):
    if gender is None:
        gender = get_partner_settings().get("gender", "女")
    return get_avatars_by_gender(gender).get(role, role)


def render_message(role, content, gender=None):
    with st.chat_message(role, avatar=get_avatar(role, gender)):
        st.markdown(content)


st.set_page_config(
    page_title="AI智能伴侣",
    layout="wide",
    page_icon="🛸",
    initial_sidebar_state="expanded",
    menu_items={},
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 920px;
        padding-top: 2rem;
        padding-bottom: 6rem;
    }
    .app-header {
        text-align: center;
        padding: 1.2rem 0 1.8rem;
        margin-bottom: 0.5rem;
    }
    .app-header h1 {
        margin: 0;
        font-size: 2rem;
        background: linear-gradient(90deg, #ff6b9d, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .empty-chat {
        text-align: center;
        padding: 3rem 1rem;
        border: 1px dashed #374151;
        border-radius: 16px;
        color: #9ca3af;
        background: rgba(255, 255, 255, 0.02);
    }
    div[data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 0.4rem 0.2rem;
    }
    div[data-testid="stChatMessageAvatar"] {
        width: 72px;
        height: 72px;
        min-width: 72px;
        flex-shrink: 0;
    }
    div[data-testid="stChatMessageAvatar"] img {
        width: 72px;
        height: 72px;
        object-fit: cover;
        border-radius: 50%;
    }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
    }
    div[data-testid="stSidebar"] img {
        width: 140px !important;
        height: 140px !important;
        border-radius: 50%;
        object-fit: cover;
        border: 3px solid #ff6b9d;
        box-shadow: 0 8px 24px rgba(255, 107, 157, 0.25);
    }
    .conv-meta {
        color: #9ca3af;
        font-size: 0.75rem;
        margin-top: 0.15rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

init_conversations_state()
active_conversation = get_active_conversation()
messages = active_conversation["messages"]
partner = get_partner_settings()
partner_name = partner["name"]
partner_personality = partner["personality"]
partner_gender = partner.get("gender", "女")
partner_gender_custom = partner.get("gender_custom", "")
system_prompt = build_system_prompt(
    partner_name, partner_personality, partner_gender, partner_gender_custom
)
partner_avatar = get_avatar("assistant", partner_gender)

with st.sidebar:
    st.image(partner_avatar, width=140)

    st.markdown("#### 伴侣设定")
    edited_name = st.text_input("名称", value=partner_name, placeholder="给小甜甜起个名字")
    edited_gender = st.selectbox(
        "性别",
        GENDER_OPTIONS,
        index=GENDER_OPTIONS.index(partner_gender) if partner_gender in GENDER_OPTIONS else 0,
    )
    edited_gender_custom = ""
    if edited_gender == "其他":
        edited_gender_custom = st.text_input(
            "其他性别",
            value=partner_gender_custom,
            placeholder="请输入自定义性别",
        )
    edited_personality = st.text_area(
        "性格",
        value=partner_personality,
        placeholder="描述一下 TA 的性格",
        height=100,
    )
    if st.button("保存设定", use_container_width=True):
        save_partner_settings(
            edited_name, edited_personality, edited_gender, edited_gender_custom
        )
        st.rerun()

    st.caption(f"你的专属搭子 · {edited_name.strip() or partner_name}")

    st.markdown("---")
    if st.button("＋ 新建对话", type="primary", use_container_width=True):
        create_conversation()
        st.rerun()

    st.markdown("#### 对话列表")
    sorted_conversations = sorted(
        st.session_state.conversations_data["items"],
        key=lambda item: item["updated_at"],
        reverse=True,
    )

    for conversation in sorted_conversations:
        is_active = conversation["id"] == st.session_state.conversations_data["active_id"]
        col_select, col_delete = st.columns([5, 1])
        with col_select:
            if st.button(
                conversation["title"],
                key=f"open_{conversation['id']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                switch_conversation(conversation["id"])
                st.rerun()
        with col_delete:
            if st.button("🗑", key=f"delete_{conversation['id']}", help="删除对话"):
                delete_conversation(conversation["id"])
                st.rerun()

        if is_active:
            st.caption(f"当前 · {len(conversation['messages'])} 条消息")

st.markdown(
    """
    <div class="app-header">
        <h1>AI 智能伴侣</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(f"当前对话：{active_conversation['title']}")

if not messages:
    st.markdown(
        """
        <div class="empty-chat">
            还没有聊天记录，在下方输入框开始第一句吧 ✨
        </div>
        """,
        unsafe_allow_html=True,
    )

for message in messages:
    render_message(message["role"], message["content"], partner_gender)

prompt = st.chat_input(f"和{partner_name}说点什么...")

if prompt:
    messages.append({"role": "user", "content": prompt})
    render_message("user", prompt, partner_gender)

    with st.chat_message("assistant", avatar=get_avatar("assistant", partner_gender)):
        reply_box = st.empty()
        with st.status(f"{partner_name}正在思考...", expanded=False) as status:
            stream = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages,
                ],
                stream=True,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
            )

            reply = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    if not reply:
                        status.update(label=f"{partner_name}开始回答了", state="running")
                    reply += delta.content
                    reply_box.markdown(reply + "▌")

            if reply:
                reply_box.markdown(reply)
                status.update(label="回答完成", state="complete")
            else:
                reply_box.warning("这次没想好怎么回，你再问一次？")
                status.update(label="回答失败", state="error")

    messages.append({"role": "assistant", "content": reply})
    update_active_conversation(messages)
