import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-buildopt-secret",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  const secret = Deno.env.get("BUILDOPT_WEBHOOK_SECRET");
  if (secret && req.headers.get("x-buildopt-secret") !== secret) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const alert = await req.json();
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const row = {
      id: alert.id,
      building_id: alert.building_id,
      equipment_id: alert.equipment_id ?? null,
      severity: alert.severity,
      category: alert.category,
      title: alert.title,
      message: alert.message,
      message_ar: alert.message_ar ?? alert.message,
      acknowledged: alert.acknowledged ?? false,
      created_at: alert.timestamp ?? new Date().toISOString(),
    };

    for (const table of ["building_alerts", "alerts"]) {
      const { error } = await supabase.from(table).upsert(row);
      if (!error) {
        return new Response(JSON.stringify({ success: true, table }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
    }

    throw new Error("Could not upsert alert to building_alerts or alerts");
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
