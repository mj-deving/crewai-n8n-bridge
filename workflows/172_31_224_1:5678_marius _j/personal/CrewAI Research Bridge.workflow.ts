import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : CrewAI Research Bridge
// Nodes   : 3  |  Connections: 2
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// WebhookTrigger                     webhook
// KickoffResearchCrew                httpRequest
// RespondToWebhook                   respondToWebhook
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// WebhookTrigger
//    → KickoffResearchCrew
//      → RespondToWebhook
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'c5z4alHyMVfdltp0',
    name: 'CrewAI Research Bridge',
    active: false,
    settings: { executionOrder: 'v1', callerPolicy: 'workflowsFromSameOwner', availableInMCP: false },
})
export class CrewaiResearchBridgeWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'ef4d6d35-bf32-4e5b-a7a8-17ccf0918a86',
        webhookId: '02adfe5f-55f6-46b3-a22b-d5d9b5c5ad8f',
        name: 'Webhook Trigger',
        type: 'n8n-nodes-base.webhook',
        version: 2,
        position: [200, 300],
    })
    WebhookTrigger = {
        httpMethod: 'POST',
        path: 'research-request',
        options: {},
    };

    @node({
        id: 'f64af5ee-e7e7-4efd-9aed-0437a9fae75c',
        name: 'Kickoff Research Crew',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [420, 300],
    })
    KickoffResearchCrew = {
        method: 'POST',
        url: 'http://172.31.224.1:8000/crews/research/kickoff',
        sendBody: true,
        specifyBody: 'json',
        jsonBody: '={{ JSON.stringify({ topic: $json.body.topic, callback_url: "" }) }}',
        options: {},
    };

    @node({
        id: '7e72f98d-e241-4846-85a4-e0eda6f5ea9e',
        name: 'Respond to Webhook',
        type: 'n8n-nodes-base.respondToWebhook',
        version: 1.1,
        position: [640, 300],
    })
    RespondToWebhook = {
        respondWith: 'json',
        responseBody:
            '={{ JSON.stringify({ message: "Research crew started", task_id: $json.task_id, status: $json.status }) }}',
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.WebhookTrigger.out(0).to(this.KickoffResearchCrew.in(0));
        this.KickoffResearchCrew.out(0).to(this.RespondToWebhook.in(0));
    }
}
