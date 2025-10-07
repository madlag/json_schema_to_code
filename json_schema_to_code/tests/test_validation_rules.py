"""
Unit tests for validation rule objects.
"""

import unittest

from json_schema_to_code.validation_rules import (
    ArrayItemTypeRule,
    ConstRule,
    EnumRule,
    ExclusiveMaximumRule,
    ExclusiveMinimumRule,
    MaximumRule,
    MaxItemsRule,
    MaxLengthRule,
    MinimumRule,
    MinItemsRule,
    MinLengthRule,
    MultipleOfRule,
    NonEmptyStringRule,
    PatternRule,
    ReferenceTypeCheckRule,
    TypeCheckRule,
)


class TestValidationRulesPython(unittest.TestCase):
    """Test validation rules for Python code generation"""

    def test_type_check_rule_python(self):
        rule = TypeCheckRule("age", "python", "int")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("isinstance(self.age, int)", code[0])
        self.assertIn("raise ValueError", code[1])

    def test_reference_type_check_rule_python(self):
        rule = ReferenceTypeCheckRule("address", "python", "Address")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("isinstance(self.address, Address)", code[0])
        self.assertIn("Address instance", code[1])

    def test_non_empty_string_rule_python(self):
        rule = NonEmptyStringRule("name", "python")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("if not self.name:", code[0])
        self.assertIn("required and cannot be empty", code[1])

    def test_pattern_rule_python(self):
        rule = PatternRule("email", "python", "^[a-z]+@[a-z]+\\.[a-z]+$")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        # Should use raw string without double-escaping backslashes
        self.assertEqual(code[0], 'if not re.match(r"^[a-z]+@[a-z]+\\.[a-z]+$", self.email):')
        self.assertIn("must match pattern", code[1])

    def test_min_length_rule_python(self):
        rule = MinLengthRule("username", "python", 3)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("len(self.username) < 3", code[0])
        self.assertIn("at least 3 characters", code[1])

    def test_max_length_rule_python(self):
        rule = MaxLengthRule("username", "python", 20)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("len(self.username) > 20", code[0])
        self.assertIn("at most 20 characters", code[1])

    def test_minimum_rule_python(self):
        rule = MinimumRule("age", "python", 0)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("self.age < 0", code[0])
        self.assertIn("must be >= 0", code[1])

    def test_maximum_rule_python(self):
        rule = MaximumRule("age", "python", 150)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("self.age > 150", code[0])
        self.assertIn("must be <= 150", code[1])

    def test_exclusive_minimum_rule_python(self):
        rule = ExclusiveMinimumRule("temperature", "python", -273.15)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("self.temperature <= -273.15", code[0])
        self.assertIn("must be > -273.15", code[1])

    def test_exclusive_maximum_rule_python(self):
        rule = ExclusiveMaximumRule("percentage", "python", 100)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("self.percentage >= 100", code[0])
        self.assertIn("must be < 100", code[1])

    def test_multiple_of_rule_python(self):
        rule = MultipleOfRule("even_number", "python", 2)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("self.even_number % 2 != 0", code[0])
        self.assertIn("must be a multiple of 2", code[1])

    def test_min_items_rule_python(self):
        rule = MinItemsRule("tags", "python", 1)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("len(self.tags) < 1", code[0])
        self.assertIn("at least 1 items", code[1])

    def test_max_items_rule_python(self):
        rule = MaxItemsRule("tags", "python", 10)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("len(self.tags) > 10", code[0])
        self.assertIn("at most 10 items", code[1])

    def test_array_item_type_rule_python(self):
        rule = ArrayItemTypeRule("items", "python", "Item")
        code = rule.generate_code()
        self.assertEqual(len(code), 3)
        self.assertIn("enumerate(self.items)", code[0])
        self.assertIn("isinstance(item, Item)", code[1])

    def test_enum_rule_python(self):
        rule = EnumRule("status", "python", ["active", "inactive", "pending"])
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("'active', 'inactive', 'pending'", code[0])
        self.assertIn("must be one of", code[1])

    def test_const_rule_python(self):
        rule = ConstRule("type", "python", "user")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("self.type != 'user'", code[0])
        self.assertIn("must be 'user'", code[1])


class TestValidationRulesCSharp(unittest.TestCase):
    """Test validation rules for C# code generation"""

    def test_type_check_rule_cs(self):
        rule = TypeCheckRule("age", "cs", "int")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("Age == null", code[0])
        self.assertIn("ArgumentNullException", code[1])

    def test_reference_type_check_rule_cs(self):
        rule = ReferenceTypeCheckRule("address", "cs", "Address")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("Address == null", code[0])
        self.assertIn("is required", code[1])

    def test_non_empty_string_rule_cs(self):
        rule = NonEmptyStringRule("name", "cs")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("IsNullOrEmpty(Name)", code[0])
        self.assertIn("required and cannot be empty", code[1])

    def test_pattern_rule_cs(self):
        rule = PatternRule("email", "cs", "^[a-z]+@[a-z]+\\.[a-z]+$")
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("Regex.IsMatch", code[0])
        self.assertIn("must match pattern", code[1])

    def test_min_length_rule_cs(self):
        rule = MinLengthRule("username", "cs", 3)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("Username.Length < 3", code[0])
        self.assertIn("at least 3 characters", code[1])

    def test_maximum_rule_cs(self):
        rule = MaximumRule("age", "cs", 150)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("Age > 150", code[0])
        self.assertIn("must be <= 150", code[1])

    def test_min_items_rule_cs(self):
        rule = MinItemsRule("tags", "cs", 1)
        code = rule.generate_code()
        self.assertEqual(len(code), 2)
        self.assertIn("Tags.Count < 1", code[0])
        self.assertIn("at least 1 items", code[1])

    def test_enum_rule_cs(self):
        rule = EnumRule("status", "cs", ["active", "inactive"])
        code = rule.generate_code()
        self.assertEqual(len(code), 3)
        self.assertIn("validStatusValues", code[0])
        self.assertIn("Contains(Status)", code[1])


if __name__ == "__main__":
    unittest.main()
