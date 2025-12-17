using System;
using Newtonsoft.Json;

[Serializable]
public class BaseClass
{
    [JsonProperty("id")]
    public int Id { get; set; }

    public BaseClass(int id)
    {
        this.Id = id;
    }

    public BaseClass() { }
}

[Serializable]
public class DerivedClass : BaseClass
{
    [JsonProperty("name")]
    public string Name { get; set; }

    public DerivedClass(int id, string name): base(id)
    {
        this.Name = name;
    }

    public DerivedClass() { }
}
