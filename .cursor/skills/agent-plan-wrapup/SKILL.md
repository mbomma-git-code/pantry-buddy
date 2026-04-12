# Agent Plan Wrapup Skill

# Description 
Use when the user wants to mark all the tasks as done for the cursor plan that is generated. 

# Instructions
1. Verify if all the tasks in the plan are completed. If any task is not completed, report back with the name of the task. Stop the skill execution here.
2. If all the tasks are completed, mark all the tasks in the plan as done.
3. isProject: true in that saved plan so it now lives as a project plan in the repo.
4. Save this plan in the cursor plan ".cursor/plans" folder in the project.
5. Push the change to mainline with the relavant commit title.