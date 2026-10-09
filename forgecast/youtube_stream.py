"""Official YouTube StreamList transport; no periodic chat-list polling.

Protocol: https://developers.google.com/youtube/v3/live/streaming-live-chat
"""
import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import grpc
from google.protobuf.json_format import MessageToDict
from .youtube_proto import stream_list_pb2 as proto


METHOD = '/youtube.api.v3.V3DataLiveChatMessageService/StreamList'
TYPES = {1:'textMessageEvent', 2:'tombstone', 3:'fanFundingEvent',
         4:'chatEndedEvent', 5:'sponsorOnlyModeStartedEvent',
         6:'sponsorOnlyModeEndedEvent', 7:'newSponsorEvent', 10:'userBannedEvent',
         15:'superChatEvent', 16:'superStickerEvent', 17:'memberMilestoneChatEvent',
         18:'membershipGiftingEvent', 19:'giftMembershipReceivedEvent',
         20:'pollEvent', 21:'giftEvent'}


def response_dict(response):
    """Convert protobuf enum names to the existing REST message representation."""
    result = MessageToDict(response, use_integers_for_enums=True)
    for item in result.get('items', []):
        snippet = item.get('snippet', {})
        snippet['type'] = TYPES.get(snippet.get('type'), 'unknownEvent')
        banned = snippet.get('userBannedDetails')
        if banned and 'banType' in banned:
            banned['banType'] = {1:'permanent', 2:'temporary'}.get(banned['banType'], 'unknown')
    return result


def quota_retry_seconds(now=None):
    """Wait until the next project-quota reset, including Pacific DST."""
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo('America/Los_Angeles'))
    reset = (local + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
    return max(60, (reset.astimezone(timezone.utc) - now).total_seconds())


async def stream_responses(chat_id, token, page=None):
    # This channel has its own lifetime; the Hub's 15-second HTTP timeout must
    # never close a healthy, quiet live chat. OAuth changes reopen the channel.
    async with grpc.aio.secure_channel('youtube.googleapis.com:443', grpc.ssl_channel_credentials(),
            options=[('grpc.max_receive_message_length', 8*1024*1024)]) as channel:
        await asyncio.wait_for(channel.channel_ready(), 30)
        method = channel.unary_stream(METHOD,
            request_serializer=proto.LiveChatMessageListRequest.SerializeToString,
            response_deserializer=proto.LiveChatMessageListResponse.FromString)
        request = proto.LiveChatMessageListRequest(live_chat_id=chat_id,
            part=['id', 'snippet', 'authorDetails'], profile_image_size=48)
        if page: request.page_token = page
        call = method(request, metadata=(('authorization', 'Bearer '+token),))
        try:
            async for response in call:
                yield response_dict(response)
        finally:
            call.cancel()


def stream_error(exc):
    """Return only known safe error categories; never expose RPC details/tokens."""
    code = exc.code()
    if code == grpc.StatusCode.UNAUTHENTICATED: return 'authorization'
    if code == grpc.StatusCode.PERMISSION_DENIED: return 'permission'
    if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
        # RESOURCE_EXHAUSTED alone also covers rate limiting. Unknown exhaustion
        # is retried slowly; only explicit quota indicators wait for daily reset.
        detail = (exc.details() or '').lower()
        return 'quota' if 'quota' in detail or 'daily' in detail else 'limit'
    if code == grpc.StatusCode.NOT_FOUND: return 'not_found'
    if code == grpc.StatusCode.FAILED_PRECONDITION: return 'ended_or_disabled'
    if code == grpc.StatusCode.INVALID_ARGUMENT: return 'invalid_cursor'
    if code == grpc.StatusCode.UNIMPLEMENTED: return 'unsupported'
    return 'network'
