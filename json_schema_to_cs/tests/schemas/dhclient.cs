using System;
using System.Collections.Generic;
using JsonSubTypes;
using Newtonsoft.Json;

[Serializable]
[JsonConverter(typeof(JsonSubtypes), "type")]
[JsonSubtypes.KnownSubType(typeof(DHMError), "DHMError")]
[JsonSubtypes.KnownSubType(typeof(DHMChatInfo), "DHMChatInfo")]
[JsonSubtypes.KnownSubType(typeof(DHMSetChatView), "DHMSetChatView")]
[JsonSubtypes.KnownSubType(typeof(DHMAgentChatView), "DHMAgentChatView")]
[JsonSubtypes.KnownSubType(typeof(DHMAddHuman), "DHMAddHuman")]
[JsonSubtypes.KnownSubType(typeof(DHMAddAgent), "DHMAddAgent")]
[JsonSubtypes.KnownSubType(typeof(DHMHumanTextChunk), "DHMHumanTextChunk")]
[JsonSubtypes.KnownSubType(typeof(DHMHumanAction), "DHMHumanAction")]
[JsonSubtypes.KnownSubType(typeof(DHMHumanAudioChunk), "DHMHumanAudioChunk")]
[JsonSubtypes.KnownSubType(typeof(DHMHumanImage), "DHMHumanImage")]
[JsonSubtypes.KnownSubType(typeof(DHMAgentTextChunk), "DHMAgentTextChunk")]
[JsonSubtypes.KnownSubType(typeof(DHMAgentTimedMediaChunk), "DHMAgentTimedMediaChunk")]
[JsonSubtypes.KnownSubType(typeof(DHMAgentActionDefinition), "DHMAgentActionDefinition")]
[JsonSubtypes.KnownSubType(typeof(DHMMetadata), "DHMMetadata")]
public class DHMessage{
    public string type;
    public List<StringOrInt> id;
    public DHMessage(string type, List<StringOrInt> id)    {
        this.type = type;
        this.id = id;
    }
}
[Serializable]
public class DHMError : DHMessage
{
    public int code;
    public string codeDescription;
    public int service;
    public string serviceDescription;
    public int serviceProvider;
    public string serviceProviderDescription;
    public string message;
    public DHMError(List<StringOrInt> id, int code, string codeDescription, int service, string serviceDescription, int serviceProvider, string serviceProviderDescription, string message): base("DHMError", id)
    {
        this.code = code;
        this.codeDescription = codeDescription;
        this.service = service;
        this.serviceDescription = serviceDescription;
        this.serviceProvider = serviceProvider;
        this.serviceProviderDescription = serviceProviderDescription;
        this.message = message;
    }
}
[Serializable]
public class DHMChatInfo : DHMessage
{
    public DHMChatInfo(List<StringOrInt> id): base("DHMChatInfo", id)
    {
    }
}
[Serializable]
public class DHMSetChatView : DHMessage
{
    public ChatViewConfig view;
    public DHMSetChatView(List<StringOrInt> id, ChatViewConfig view): base("DHMSetChatView", id)
    {
        this.view = view;
    }
}
[Serializable]
public class DHMAgentChatView : DHMessage
{
    public int agentId;
    public ChatViewInfo view;
    public DHMAgentChatView(List<StringOrInt> id, int agentId, ChatViewInfo view): base("DHMAgentChatView", id)
    {
        this.agentId = agentId;
        this.view = view;
    }
}
[Serializable]
public class DHMAddHuman : DHMessage
{
    public int humanId;
    public DHMAddHuman(List<StringOrInt> id, int humanId): base("DHMAddHuman", id)
    {
        this.humanId = humanId;
    }
}
[Serializable]
public class DHMAddAgent : DHMessage
{
    public int agentId;
    public DHMAddAgent(List<StringOrInt> id, int agentId): base("DHMAddAgent", id)
    {
        this.agentId = agentId;
    }
}
[Serializable]
public class DHMHumanTextChunk : DHMessage
{
    public int humanId;
    public string text;
    public bool final;
    public DHMHumanTextChunk(List<StringOrInt> id, int humanId, string text, bool final): base("DHMHumanTextChunk", id)
    {
        this.humanId = humanId;
        this.text = text;
        this.final = final;
    }
}
[Serializable]
public class DHMHumanAction : DHMessage
{
    public int humanId;
    public string actionType;
    public string action;
    public DHMHumanAction(List<StringOrInt> id, int humanId, string actionType, string action): base("DHMHumanAction", id)
    {
        this.humanId = humanId;
        this.actionType = actionType;
        this.action = action;
    }
}
[Serializable]
public class DHMHumanAudioChunk : DHMessage
{
    public int humanId;
    public string buffer;
    public int sampleIndex;
    public int sampleRate;
    public int channels;
    public string format;
    public bool final;
    public string language;
    public DHMHumanAudioChunk(List<StringOrInt> id, int humanId, string buffer, int sampleIndex, int sampleRate, int channels, string format, bool final, string language): base("DHMHumanAudioChunk", id)
    {
        this.humanId = humanId;
        this.buffer = buffer;
        this.sampleIndex = sampleIndex;
        this.sampleRate = sampleRate;
        this.channels = channels;
        this.format = format;
        this.final = final;
        this.language = language;
    }
}
[Serializable]
public class DHMHumanImage : DHMessage
{
    public int humanId;
    public string text;
    public string url;
    public DHMHumanImage(List<StringOrInt> id, int humanId, string text, string url): base("DHMHumanImage", id)
    {
        this.humanId = humanId;
        this.text = text;
        this.url = url;
    }
}
[Serializable]
public class DHMAgentTextChunk : DHMessage
{
    public int agentId;
    public string text;
    public bool final;
    public bool system;
    public DHMAgentTextChunk(List<StringOrInt> id, int agentId, string text, bool final, bool system): base("DHMAgentTextChunk", id)
    {
        this.agentId = agentId;
        this.text = text;
        this.final = final;
        this.system = system;
    }
}
[Serializable]
public class DHMAgentTimedMediaChunk : DHMessage
{
    public int agentId;
    public List<TimedMedia> timedMedia;
    public DHMAgentTimedMediaChunk(List<StringOrInt> id, int agentId, List<TimedMedia> timedMedia): base("DHMAgentTimedMediaChunk", id)
    {
        this.agentId = agentId;
        this.timedMedia = timedMedia;
    }
}
[Serializable]
[JsonConverter(typeof(JsonSubtypes), "type")]
[JsonSubtypes.KnownSubType(typeof(TimedAudio), "TimedAudio")]
[JsonSubtypes.KnownSubType(typeof(TimedViseme), "TimedViseme")]
[JsonSubtypes.KnownSubType(typeof(TimedText), "TimedText")]
[JsonSubtypes.KnownSubType(typeof(TimedAction), "TimedAction")]
[JsonSubtypes.KnownSubType(typeof(TimedMetadata), "TimedMetadata")]
public class TimedMedia{
    public string type;
    public float time;
    public float duration;
    public TimedMedia(string type, float time, float duration)    {
        this.type = type;
        this.time = time;
        this.duration = duration;
    }
}
[Serializable]
public class TimedAudio : TimedMedia
{
    public string buffer;
    public int sampleIndex;
    public int sampleRate;
    public int channels;
    public int audioByteSize;
    public TimedAudio(float time, float duration, string buffer, int sampleIndex, int sampleRate, int channels, int audioByteSize): base("TimedAudio", time, duration)
    {
        this.buffer = buffer;
        this.sampleIndex = sampleIndex;
        this.sampleRate = sampleRate;
        this.channels = channels;
        this.audioByteSize = audioByteSize;
    }
}
[Serializable]
public class TimedViseme : TimedMedia
{
    public string viseme;
    public TimedViseme(float time, float duration, string viseme): base("TimedViseme", time, duration)
    {
        this.viseme = viseme;
    }
}
[Serializable]
public class TimedText : TimedMedia
{
    public string textType;
    public string text;
    public TimedText(float time, float duration, string textType, string text): base("TimedText", time, duration)
    {
        this.textType = textType;
        this.text = text;
    }
}
[Serializable]
public class ActionDefinition{
    public string type;
    public List<List<string>> attributes;
    public ActionDefinition(string type, List<List<string>> attributes)    {
        this.type = type;
        this.attributes = attributes;
    }
}
[Serializable]
public class TimedAction : TimedMedia
{
    public string span;
    public int startId;
    public int endId;
    public string actionId;
    public ActionDefinition actionDefinition;
    public TimedAction(float time, float duration, string span, int startId, int endId, string actionId, ActionDefinition actionDefinition): base("TimedAction", time, duration)
    {
        this.span = span;
        this.startId = startId;
        this.endId = endId;
        this.actionId = actionId;
        this.actionDefinition = actionDefinition;
    }
}
[Serializable]
public class TimedMetadata : TimedMedia
{
    public int? totalAudioSamples;
    public int sampleRate;
    public int channels;
    public int totalAudioByteSize;
    public bool final;
    public TimedMetadata(float time, float duration, int? totalAudioSamples, int sampleRate, int channels, int totalAudioByteSize, bool final): base("TimedMetadata", time, duration)
    {
        this.totalAudioSamples = totalAudioSamples;
        this.sampleRate = sampleRate;
        this.channels = channels;
        this.totalAudioByteSize = totalAudioByteSize;
        this.final = final;
    }
}
[Serializable]
public class DHMAgentActionDefinition : DHMessage
{
    public int agentId;
    public string actionId;
    public ActionDefinition actionDefinition;
    public DHMAgentActionDefinition(List<StringOrInt> id, int agentId, string actionId, ActionDefinition actionDefinition): base("DHMAgentActionDefinition", id)
    {
        this.agentId = agentId;
        this.actionId = actionId;
        this.actionDefinition = actionDefinition;
    }
}
[Serializable]
public class DHMMetadata : DHMessage
{
    public List<List<string>> metadata;
    public DHMMetadata(List<StringOrInt> id, List<List<string>> metadata): base("DHMMetadata", id)
    {
        this.metadata = metadata;
    }
}
[Serializable]
public class ChatViewTextConfig{
    public bool enabled;
    public bool source;
    public ChatViewTextConfig(bool enabled, bool source)    {
        this.enabled = enabled;
        this.source = source;
    }
}
[Serializable]
public class ChatViewSpeechConfig{
    public bool enabled;
    public ChatViewSpeechConfig(bool enabled)    {
        this.enabled = enabled;
    }
}
[Serializable]
public class ChatViewVisemeConfig{
    public bool enabled;
    public ChatViewVisemeConfig(bool enabled)    {
        this.enabled = enabled;
    }
}
[Serializable]
public class ChatViewConfig{
    public string language;
    public ChatViewTextConfig text;
    public ChatViewSpeechConfig speech;
    public ChatViewVisemeConfig viseme;
    public ChatViewConfig(string language, ChatViewTextConfig text, ChatViewSpeechConfig speech, ChatViewVisemeConfig viseme)    {
        this.language = language;
        this.text = text;
        this.speech = speech;
        this.viseme = viseme;
    }
}
[Serializable]
public class ChatViewTextInfo{
    public bool enabled;
    public bool source;
    public ChatViewTextInfo(bool enabled, bool source)    {
        this.enabled = enabled;
        this.source = source;
    }
}
[Serializable]
public class ChatViewSpeechInfo{
    public bool enabled;
    public float sampleRate;
    public float channels;
    public float bitsPerSample;
    public string format;
    public ChatViewSpeechInfo(bool enabled, float sampleRate, float channels, float bitsPerSample, string format)    {
        this.enabled = enabled;
        this.sampleRate = sampleRate;
        this.channels = channels;
        this.bitsPerSample = bitsPerSample;
        this.format = format;
    }
}
[Serializable]
public class ChatViewVisemeInfo{
    public bool enabled;
    public ChatViewVisemeInfo(bool enabled)    {
        this.enabled = enabled;
    }
}
[Serializable]
public class ChatViewInfo{
    public string language;
    public ChatViewTextInfo text;
    public ChatViewSpeechInfo speech;
    public ChatViewVisemeInfo viseme;
    public ChatViewInfo(string language, ChatViewTextInfo text, ChatViewSpeechInfo speech, ChatViewVisemeInfo viseme)    {
        this.language = language;
        this.text = text;
        this.speech = speech;
        this.viseme = viseme;
    }
}
