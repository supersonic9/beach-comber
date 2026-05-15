---
name: new-project 
description: Create a replica of the current directory (claude-project-template) with the same structure and files, and fill in the SCOPE.md file with the proposed plan 
---

# Implement Next Phase

1. Currently we are in the directory `claude-project-template`. Create a new directory with the same structure and files as `claude-project-template`. Ask the user what the name of the new directory should be 
2. Copy all files and subdirectories from `claude-project-template` to the new directory.
3. Open the `SCOPE.md` file in the new directory and fill it in with the proposed plan for the project in such a way that the implementation is broken clearly into phases which can be easily implemented by Claude Code in subsequent steps. 