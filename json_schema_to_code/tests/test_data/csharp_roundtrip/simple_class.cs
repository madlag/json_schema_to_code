using System;
using Newtonsoft.Json;

[Serializable]
public class SimpleClass
{
    [JsonProperty("name")]
    public string Name { get; set; }

    [JsonProperty("age")]
    public int Age { get; set; }

    [JsonProperty("is_active")]
    public bool IsActive { get; set; }

    public SimpleClass(string name, int age, bool isActive)
    {
        this.Name = name;
        this.Age = age;
        this.IsActive = isActive;
    }

    public SimpleClass() { }
}
