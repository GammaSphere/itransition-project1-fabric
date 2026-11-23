# Setup

How to get this project running in your own Microsoft Fabric workspace.

## 1. Connect the workspace to the repository

**Prerequisites**

- A Fabric workspace on a Fabric capacity (F2 or larger, or a trial). You must be a workspace **Admin**.
- In the Fabric admin portal, tenant settings: *Users can synchronize workspace items with their
  Git repositories* and *Users can sync workspace items with GitHub repositories* are enabled.
- A GitHub personal access token for this repository: fine-grained with **Contents: Read and
  write**, or classic with the `repo` scope.

**Steps**

1. Open the workspace → **Workspace settings** → **Git integration**.
2. Choose **GitHub**, add an account with the token, then select this repository, the `main`
   branch, and the Git folder `fabric`.
3. Select **Connect and sync**. Fabric creates every item found in the `fabric/` folder.

**Expected result**

| Item | Type |
|---|---|
| `lh_bronze` | Lakehouse |
| `lh_silver` | Lakehouse |
| `wh_gold` | Warehouse |
| `nb_taxi_months` | Notebook |
| `pl_master` | Data pipeline |

Only item definitions are stored in Git. Lakehouse files and tables are created when the
pipelines run.

### Logical IDs

Items reference each other by the `logicalId` in their `.platform` file.

| Item | logicalId |
|---|---|
| `lh_bronze` | `56ee5e9d-de82-46ba-9c2a-190af8a6d796` |
| `lh_silver` | `55c5c018-53e6-408c-a69f-b73edc2d0a03` |
| `wh_gold` | `35ce5df0-9823-49de-94f9-8aeeb4f0bddb` |
| `nb_taxi_months` | `fea386de-5bb4-443b-b7bf-4595c48d8420` |
| `pl_master` | `76fcb2d5-e7a8-4c1d-9c1c-7231b1e318fa` |
