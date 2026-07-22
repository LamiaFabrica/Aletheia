$(document).ready(function() {
    // --- Tools Table --- 
    $('#toolsTable').DataTable({
        "processing": true,
        "serverSide": true,
        "ajax": {
            "url": "/api/admin/db/search/tools",
            "type": "GET",
            "dataSrc": function(json) {
                // The API returns data in json.rows
                // Also adapt total records for DataTables pagination
                json.recordsTotal = json.total;
                json.recordsFiltered = json.total;
                return json.rows;
            },
            "error": function(xhr, error, thrown) {
                console.error("Error fetching tools:", error, thrown);
                alert("Could not load tools data. See console for details.");
            }
        },
        "columns": [
            { "data": "id" },
            { "data": "tool_name" },
            { "data": "description" },
            { "data": "supported_os" },
            { "data": "medusa_id" }
        ],
        "pageLength": 10,
        "lengthMenu": [[10, 25, 50, 100], [10, 25, 50, 100]]
    });

    // --- Vulnerabilities Table --- 
    $('#vulnerabilitiesTable').DataTable({
        "processing": true,
        "serverSide": true,
        "ajax": {
            "url": "/api/admin/db/search/vulnerabilities",
            "type": "GET",
            "dataSrc": function(json) {
                json.recordsTotal = json.total;
                json.recordsFiltered = json.total;
                return json.rows;
            },
            "error": function(xhr, error, thrown) {
                console.error("Error fetching vulnerabilities:", error, thrown);
                alert("Could not load vulnerabilities data. See console for details.");
            }
        },
        "columns": [
            { "data": "medusa_id" },
            { "data": "cve_id" },
            { "data": "state" },
            { "data": "assigner_short_name" },
            { "data": "date_published" },
            { "data": "date_updated" },
            { "data": "description", "width": "30%" }, // Give description more width
            { "data": "cvss_v3_base_score" },
            { "data": "cvss_v3_vector" },
            { "data": "cvss_v3_severity" }
        ],
        "pageLength": 10,
        "lengthMenu": [[10, 25, 50, 100], [10, 25, 50, 100]],
        "order": [[4, "desc"]] // Default sort by date_published descending
    });

    // --- Crawler Tool Queue Table --- 
    $('#crawlerQueueTable').DataTable({
        "processing": true,
        "serverSide": false, // Data fetched once, then client-side processing
        "ajax": {
            "url": "/api/crawler/queue", // Endpoint for crawler queue
            "type": "GET",
            "dataSrc": function(json) {
                // API returns {status: "ok", row_count: X, jobs: []}
                if (json.status === 'ok') {
                    return json.jobs;
                } else {
                    console.error("Error fetching crawler queue:", json.error);
                    alert("Could not load crawler queue data. See console for details.");
                    return [];
                }
            },
            "error": function(xhr, error, thrown) {
                console.error("Error fetching crawler queue:", error, thrown);
                alert("Could not load crawler queue data. See console for details.");
            }
        },
        "columns": [
            { "data": "id" },
            { "data": "tool_name" },
            { "data": "target_url" },
            { "data": "status" },
            { "data": "parser_hint" },
            { "data": "last_crawled_at" },
            { "data": "priority" },
            { "data": "completion_percentage", "name": "completion_perc" } // Ensure correct mapping if API uses completion_perc
        ],
        "pageLength": 10,
        "lengthMenu": [[10, 25, 50, 100], [10, 25, 50, 100]]
    });
}); 