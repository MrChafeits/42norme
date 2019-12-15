# **42norme**

42 (SiliconValley)

### **Description**

**42norme** is a python implementation of the official 42 **norminette**.

### **Requirements**

+ See requirements.txt

### **Usage**

Just run:

```bash
python3 norminette.py
```

For a convient alias insert this into your shell's respective `.rc` file:

`alias pynorme="/path/to/norminette.py"`

Run `/path/to/norminette.py --help` to view all supported rules and usage

### **Notes**

+ This script requires an active connection to the local 42 campus Wi-Fi, which is tested by performing a dns lookup on the local `vogsphere` domain

+ Some rules appear to be non-functional or poorly named, such as:
  * **`CheckVla`** which doesn't seem catch any instance of a variable length array
  * **`CheckParentSpacing`** which checks for spacing around parentheses
  * **`CheckDeclarationCount`** which doesn't seem to check the number of function declarations or variable declarations
  * **`CheckDefine`** which incorrectly interprets `#define ZERO (0)` as an invalid constant and does not understand C preprocessor string concatenation

### **Credits**

+ [@lefta](https://github.com/lefta)

### **License**

This work is published under the terms of **[42 Unlicense](https://github.com/gcamerli/42unlicense)**.
