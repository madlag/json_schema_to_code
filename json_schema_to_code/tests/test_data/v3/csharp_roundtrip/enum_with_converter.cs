using System;
using System.Collections.Generic;
using Newtonsoft.Json;

[JsonConverter(typeof(StatusJsonConverter))]
public enum Status
{
    Active,

    Inactive,

    Pending,
}

public class StatusJsonConverter : JsonConverter<Status>
{
    private static readonly Dictionary<string, Status> StringToEnum = new Dictionary<string, Status>
    {
        { "active", Status.Active },
        { "inactive", Status.Inactive },
        { "pending", Status.Pending }
    };

    private static readonly Dictionary<Status, string> EnumToString = new Dictionary<Status, string>
    {
        { Status.Active, "active" },
        { Status.Inactive, "inactive" },
        { Status.Pending, "pending" }
    };

    public override void WriteJson(JsonWriter writer, Status value, JsonSerializer serializer)
    {
        writer.WriteValue(EnumToString[value]);
    }

    public override Status ReadJson(JsonReader reader, Type objectType, Status existingValue, bool hasExistingValue, JsonSerializer serializer)
    {
        string stringValue = (string)reader.Value;
        return StringToEnum[stringValue];
    }
}
