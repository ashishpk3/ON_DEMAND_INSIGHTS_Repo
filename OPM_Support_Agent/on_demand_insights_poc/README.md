# On-demand Python insights POC

End-to-end pattern: **Salesforce Agent topic → Invocable Apex (callout) → FastAPI/Python → JSON insights** suitable for workloads that cannot run in Apex (pandas, scipy, notebooks, bespoke ML, etc.). Data Cloud/Snowflake can be queried from Python inside the service when you are ready—the stub uses synthetic sample stats only.

## 1. Run the Python service

```bash
cd OPM_Support_Agent/on_demand_insights_poc
pip install -r requirements.txt
INSIGHTS_PORT=8890 ON_DEMAND_INSIGHTS_API_KEY='optional-shared-secret' \
  PYTHONPATH=. uvicorn app.main:APP --host 127.0.0.1 --port 8890
```

Smoke test (another shell):

```bash
curl -s http://127.0.0.1:8890/health | jq .
curl -s -X POST http://127.0.0.1:8890/v1/insights \
  -H 'Content-Type: application/json' \
  -d '{"reportType":"dated_insight","context":{"reportDate":"2026-05-16","region":"AMER"}}' | jq .
```

Apex runs in Salesforce—it **never** reaches `localhost` on your laptop. Point **`ON_DEMAND_PY_INSIGHTS_URL`** at **public HTTPS** and add matching **Remote Site**.

### Deploy free HTTPS (Render.com)

Infrastructure is proprietary; Docker image + config here are OSS and run on Render’s free tier.

1. Push this repo to GitHub (or fork it).
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** → connect the repo → when asked for a blueprint file choose **`render-on-demand-insights-poc.yaml`** (repo root).
3. Under the web service env vars **optionally** set **`ON_DEMAND_INSIGHTS_API_KEY`** — then set the same string in **`ON_DEMAND_PY_INSIGHTS_API_KEY`** in Salesforce and keep sending header `X-Insights-Api-Key` (already wired in Apex when the label isn’t `NONE`).
4. After deploy, Render shows **`https://<name>.onrender.com`**. Put that URL (no slash) in **`ON_DEMAND_PY_INSIGHTS_URL`** and update **Remote Site** to the same origin.

From the poc folder (`Dockerfile`), you can also create a **Web Service → Docker** and set Render **Root Directory** to `OPM_Support_Agent/on_demand_insights_poc`.

### Shared hosting — anyone can chat without your laptop

The Agentforce bot and Apex live **in Salesforce**. Your FastAPI app must live **on always-on HTTPS infrastructure** (Render, another PaaS, or internal ingress). Flow:

1. **Every user** opens the agent in Salesforce (Employee Agent, Experience Cloud, Slack connector—whatever your org enables).
2. When the topic fires, **Salesforce runs Apex on Salesforce servers** and sends **`POST /v1/insights`** to **`ON_DEMAND_PY_INSIGHTS_URL`** (your deployed origin).
3. **Your laptop is never in the path.** Ngrok/cloudflared are only for developer smoke tests.

One deployed service URL typically backs **every conversation in that org** (all users hit the same Custom Label value). Optional **`ON_DEMAND_INSIGHTS_API_KEY`** on the host plus **`ON_DEMAND_PY_INSIGHTS_API_KEY`** in Salesforce prevents anonymous callers from using your endpoint if the URL leaks.

Operational notes:

- **Free Render** tiers may **cold-start** after idle; paid/minimum instances avoid wake latency for demos.
- After changing the **Render hostname**, update **Custom Label**, **Remote Site**, and redeploy/sync (`wire_python_insights_org.sh` or Setup UI).

See also `env.example` for environment variables.

### Prompt / Agent topic

Have the planner fill **`reportType`** (`dated_insight` or `summary`) and **`contextJson`** as compact JSON **including** **`reportDate`**: `YYYY-MM-DD` — e.g. `{"reportDate":"2026-05-16","region":"AMER"}`. For **`dated_insight`**, **`reportDate` is required** or FastAPI returns 400.

I can’t mint your Render hostname without logging into **your** account; the steps above produce the **`https://…`** URL you paste into the Custom Label.

## 2. Deploy Apex + labels + remote site

From `OPM_Support_Agent/opm-agent-project` (minimal component list):

```bash
sf project deploy start \
  --metadata "ApexClass:OnDemandPythonInsightsInvocable" \
  --metadata "ApexClass:OnDemandPythonInsightsInvocableTest" \
  --metadata "CustomLabel:ON_DEMAND_PY_INSIGHTS_URL" \
  --metadata "CustomLabel:ON_DEMAND_PY_INSIGHTS_API_KEY" \
  --metadata "RemoteSiteSetting:On_Demand_Python_Insights_POC" \
  --metadata "PermissionSet:On_Demand_Python_Insights_Action"
```

If you rely on **`OPM+ Analysis Admin`** or **`OPM+ Analysis Admin (Einstein Agent)`**, deploy those permission sets too after updating them in Git so **`OnDemandPythonInsightsInvocable`** is included alongside **`OPMAnalysisQuery`**.

Post-deploy in **Setup → Custom Labels**:

- **`ON_DEMAND_PY_INSIGHTS_URL`** — `https://<your-host-no-trailing-slash>`
- **`ON_DEMAND_PY_INSIGHTS_API_KEY`** — matched secret or `NONE` to skip the header

Match **Remote Site** `On_Demand_Python_Insights_POC` to that origin (duplicate if you provision multiple tiers).

Grant **Apex**: assign permission set **`On_Demand_Python_Insights_Action`**, **or** use **`OPM+ Analysis Admin (Einstein)`** / **`OPM+ Analysis Admin`**, which now include **OnDemandPythonInsightsInvocable** for continuity with the Data Cloud query action.

## 3. Standalone POC Agent (separate from OPM Support Agent)

A **dedicated** Employee Copilot was created in **`collab_ashish_sdo`** (STORM collab) so it does not share the OPM Support Agent planner bundle.

| Item | Value |
|------|--------|
| **Agent label** | Python Insights POC |
| **Bot API name** | `Py_Insights_POC_Agent` |
| **Spec file (source of truth)** | `opm-agent-project/specs/PythonInsightsPOC.agentSpec.yaml` |
| **Git metadata** | `force-app/.../bots/Py_Insights_POC_Agent/`, `genAiPlannerBundles/Py_Insights_POC_Agent/` |

**Open it directly in the browser (fastest way to “find” it):**

```bash
sf org open agent --api-name Py_Insights_POC_Agent -o collab_ashish_sdo
```

In the UI you may also browse **Einstein / Agentforce / Agents** and look for **`Python Insights POC`**.

**Important:** The topic **Python On-Demand Insights** was created from the spec **without** Apex actions. In Agent Builder, edit that topic → **Add action** → **Apex** → **`OnDemandPythonInsightsInvocable`** (*Generate on-demand insights (Python)*), then map **`reportType`** and **`contextJson`**. Ensure the integration user has the Apex class (`On_Demand_Python_Insights_Action` or equivalent) and that this org has **`OnDemandPythonInsightsInvocable`** deployed (see §2 with `-o collab_ashish_sdo`).

### Recreate this agent in another org

```bash
cd OPM_Support_Agent/opm-agent-project
sf agent create --name "Python Insights POC" \
  --api-name Py_Insights_POC_Agent \
  --spec specs/PythonInsightsPOC.agentSpec.yaml \
  -o <your-alias>
```

> **Do not** paste invocable Apex labels with parentheses into the YAML topic text—`sf agent create` may try to resolve them as actions and fail (`Action not found`). Keep the spec business-oriented; wire Apex in Agent Builder.

### If an earlier `sf agent create` partially failed

Duplicate API name errors can leave orphaned setup rows. Use a new `--api-name` (for example `Py_Insights_POC_Agent_v2`) or ask an admin to remove the half-created agent in Einstein before retrying.

---

## 4. Optional: attach the action to any other Agentforce bot

If you prefer a different bot than the POC above:

1. Open that agent in Agent Builder.
2. Add or edit a Topic, then **Actions → Apex →** **`OnDemandPythonInsightsInvocable`**.
3. Activate the agent version as required by your change process.
4. Optionally `sf project retrieve start --metadata GenAiPlannerBundle:<BundleApiName>` so Git matches the org.

## Contract

HTTP `POST /v1/insights` accepts JSON:

- **`reportType`**: e.g. `summary` or `dated_insight` (**`dated_insight` requires `reportDate`** inside `context` / `contextJson`).
- **`context`** or **`contextJson`**: object or JSON string. Date keys (first match wins): **`reportDate`**, **`asOfDate`**, **`date`**, **`forDate`** — value **`YYYY-MM-DD`** only.

Response includes **`summaryText`** plus **`insights`** (adds **`dateAnchoredInsights`** when a date is provided). Apex now serializes **`{ "reportType": "...", "context": { … } }`**, merging optional **`reportDate`** (Invocable `Date`) on top of **Context JSON** before callout.

## Automated CLI wiring — collab org

From **`opm-agent-project`** deploy **Apex** (Planner bundle stay **UI-managed** — see FAQ below):

```bash
cd OPM_Support_Agent/opm-agent-project

sf agent deactivate --api-name Py_Insights_POC_Agent -o collab_ashish_sdo

sf project deploy start \
  --metadata ApexClass:OnDemandPythonInsightsInvocable \
  --metadata ApexClass:OnDemandPythonInsightsInvocableTest \
  --metadata PermissionSet:OnDemand_Python_Insights_Apex_Only \
  -o collab_ashish_sdo

# Do NOT bulk-deploy GenAiPlannerBundle for this POC — see FAQ (duplicate topic rule).

sf agent activate --api-name Py_Insights_POC_Agent -o collab_ashish_sdo
```

### Permission sets (Einstein Agent license vs Apex-only)

- **`On_Demand_Python_Insights_Action`** declares an Einstein Agent permission-set license requirement. Salesforce rejects assignment if that user lacks the **Einstein Agent** SKU (**“Can't assign…”**).

- **`OnDemand_Python_Insights_Apex_Only`** (**no Einstein license**) exists so admins can still run **Flows / Anonymous / tests** touching the class. Deploy it with the Apex step above.

- **Agent conversations** invoke Apex as whatever **Einstein Agent / Agentforce integration** (copilot runtime) users your org configures. Assign **`On_Demand_Python_Insights_Action`** to **those** identities (often one or more Integration users set up under Einstein Agent / Agent Setup), not necessarily your human login unless that login is also the runtime user.

### FAQ: Planner deploy fails — “topic … already exists”

`sf agent create` provisioning already created topic **`p_16jId000000Kz6c_Python_On_Demand_Insights`**. Re-deploying **`localTopics`** metadata with the **same developerName** duplicates that definition → Salesforce blocks deploy.

**Stable pattern:** Git keeps Planner XML in the lean **`genAiPlugins`-only form** Git already retrieved. Attach the Apex action once in Agent Builder instead:

1. **Agent Builder** → **`Python Insights POC`** (**`Py_Insights_POC_Agent`**) → open topic **Python On-Demand Insights** (same **`p_*` id** surfaced in Planner UI).
2. **Add action → Apex →** **`OnDemandPythonInsightsInvocable`**. **Refresh Variables** → map **Report type**, **Report date anchor**, **Context JSON** (instructions from prompts).
3. Deactivate planner save if Salesforce requires it (**Agent version** deactivate / activate cycle).

(Optional) After saving in prod, **`sf project retrieve start --metadata GenAiPlannerBundle:Py_Insights_POC_Agent`** copies **UI-authoritative XML**—do **not** reintroduce conflicting duplicate topic blocks blindly.
