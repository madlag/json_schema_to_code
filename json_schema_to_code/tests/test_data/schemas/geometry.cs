using System;
using System.Collections.Generic;
using JsonSubTypes;
using Newtonsoft.Json;

[Serializable]
[JsonConverter(typeof(JsonSubtypes), "type")]
[JsonSubtypes.KnownSubType(typeof(GeometryObjectPoint), "point")]
[JsonSubtypes.KnownSubType(typeof(GeometryObjectSegment), "segment")]
[JsonSubtypes.KnownSubType(typeof(GeometryObjectLine), "line")]
[JsonSubtypes.KnownSubType(typeof(GeometryObjectRay), "ray")]
[JsonSubtypes.KnownSubType(typeof(GeometryObjectVector), "vector")]
[JsonSubtypes.KnownSubType(typeof(GeometryObjectTriangle), "triangle")]
[JsonSubtypes.KnownSubType(typeof(GeometryObjectQuadrilateral), "quadrilateral")]
[JsonSubtypes.KnownSubType(typeof(GeometryObjectCircle), "center")]
public class GeometryObject{
    public string type;
    public GeometryObject(string type)    {
        this.type = type;
    }
}
[Serializable]
public class GeometryObjectPoint : GeometryObject
{
    public string name;
    public List<float> coordinate;
    public GeometryObjectPoint(string name, List<float> coordinate): base("point")
    {
        this.name = name;
        this.coordinate = coordinate;
    }
}
[Serializable]
public class GeometryObjectSegment : GeometryObject
{
    public List<string> points;
    public GeometryObjectSegment(List<string> points): base("segment")
    {
        this.points = points;
    }
}
[Serializable]
public class GeometryObjectLine : GeometryObject
{
    public List<string> points;
    public GeometryObjectLine(List<string> points): base("line")
    {
        this.points = points;
    }
}
[Serializable]
public class GeometryObjectRay : GeometryObject
{
    public List<string> points;
    public GeometryObjectRay(List<string> points): base("ray")
    {
        this.points = points;
    }
}
[Serializable]
public class GeometryObjectVector : GeometryObject
{
    public List<string> points;
    public GeometryObjectVector(List<string> points): base("vector")
    {
        this.points = points;
    }
}
[Serializable]
public class GeometryObjectTriangle : GeometryObject
{
    public string kind;// Allowed values: "isosceles", "equilateral", "general"
    public List<string> points;
    public GeometryObjectTriangle(string kind, List<string> points): base("triangle")
    {
        this.kind = kind;
        this.points = points;
    }
}
[Serializable]
public class GeometryObjectQuadrilateral : GeometryObject
{
    public string kind;// Allowed values: "square", "rectangle", "rhombus", "parallelogram", "trapezoid", "kite", "general"
    public List<string> points;
    public GeometryObjectQuadrilateral(string kind, List<string> points): base("quadrilateral")
    {
        this.kind = kind;
        this.points = points;
    }
}
[Serializable]
public class GeometryObjectCircle : GeometryObject
{
    public string center;
    public float radius;
    public GeometryObjectCircle(string center, float radius): base("center")
    {
        this.center = center;
        this.radius = radius;
    }
}
[Serializable]
[JsonConverter(typeof(JsonSubtypes), "type")]
[JsonSubtypes.KnownSubType(typeof(ConstraintDistanceFixed), "distance_fixed")]
[JsonSubtypes.KnownSubType(typeof(ConstraintDistanceEquals), "distance_equals")]
[JsonSubtypes.KnownSubType(typeof(ConstraintAngleFixed), "angle_fixed")]
[JsonSubtypes.KnownSubType(typeof(ConstraintAngleEquals), "angle_equals")]
public class Constraint{
    public string type;
    public Constraint(string type)    {
        this.type = type;
    }
}
[Serializable]
public class ConstraintDistanceFixed : Constraint
{
    public float distance;
    public ConstraintDistanceFixed(float distance): base("distance_fixed")
    {
        this.distance = distance;
    }
}
[Serializable]
public class ConstraintDistanceEquals : Constraint
{
    public ConstraintDistanceEquals(): base("distance_equals")
    {
    }
}
[Serializable]
public class ConstraintAngleFixed : Constraint
{
    public float angle;
    public ConstraintAngleFixed(float angle): base("angle_fixed")
    {
        this.angle = angle;
    }
}
[Serializable]
public class ConstraintAngleEquals : Constraint
{
    public ConstraintAngleEquals(): base("angle_equals")
    {
    }
}
[Serializable]
public class Style{
    public string name;
    public string color;
    public float strokeWidth;
    public Style(string name, string color, float strokeWidth)    {
        this.name = name;
        this.color = color;
        this.strokeWidth = strokeWidth;
    }
}
