import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : CrewAI Callback Receiver
// Nodes   : 3  |  Connections: 2
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ReceiveCrewResult                  webhook
// ExtractResultFields                set
// RespondOk                          respondToWebhook
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ReceiveCrewResult
//    → ExtractResultFields
//      → RespondOk
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: '1hWQQPPaZEYiMNIF',
    name: 'CrewAI Callback Receiver',
    active: false,
    settings: { executionOrder: 'v1', callerPolicy: 'workflowsFromSameOwner', availableInMCP: false },
})
export class CrewaiCallbackReceiverWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'eef1d262-ae09-49a0-80da-6e610b302775',
        webhookId: '8b4bc461-78be-4079-bb08-437657ace238',
        name: 'Receive Crew Result',
        type: 'n8n-nodes-base.webhook',
        version: 2,
        position: [200, 300],
    })
    ReceiveCrewResult = {
        httpMethod: 'POST',
        path: 'crewai-callback',
        responseMode: 'responseNode',
        options: {},
    };

    @node({
        id: '260672d9-fea4-4a38-bae7-b362ff90f76d',
        name: 'Extract Result Fields',
        type: 'n8n-nodes-base.set',
        version: 3.4,
        position: [420, 300],
    })
    ExtractResultFields = {
        assignments: {
            assignments: [
                {
                    id: 'task_id',
                    name: 'task_id',
                    value: '={{ $json.body.task_id }}',
                    type: 'string',
                },
                {
                    id: 'crew_name',
                    name: 'crew_name',
                    value: '={{ $json.body.crew_name }}',
                    type: 'string',
                },
                {
                    id: 'status',
                    name: 'status',
                    value: '={{ $json.body.status }}',
                    type: 'string',
                },
                {
                    id: 'result',
                    name: 'result',
                    value: '={{ $json.body.result }}',
                    type: 'string',
                },
                {
                    id: 'duration',
                    name: 'duration_sec',
                    value: '={{ $json.body.duration_sec }}',
                    type: 'number',
                },
            ],
        },
        options: {},
    };

    @node({
        id: 'b031262c-c2d3-4a5d-9316-0e8be35a2ab1',
        name: 'Respond OK',
        type: 'n8n-nodes-base.respondToWebhook',
        version: 1.1,
        position: [640, 300],
    })
    RespondOk = {
        respondWith: 'json',
        responseBody: '={{ JSON.stringify({ received: true, task_id: $json.task_id }) }}',
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ReceiveCrewResult.out(0).to(this.ExtractResultFields.in(0));
        this.ExtractResultFields.out(0).to(this.RespondOk.in(0));
    }
}
