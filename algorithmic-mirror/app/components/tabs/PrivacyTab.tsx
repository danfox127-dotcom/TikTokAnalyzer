"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { DemographicPanel } from "../DemographicPanel";
import { ACCENT, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT, INK_DIM, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

export function PrivacyTab({ profile }: { profile: GhostProfile }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      <DashboardPanel label="09 · Digital Footprint" accent={ACCENT}>
        <SectionTitle>Geographic & Device Trace</SectionTitle>
        <div className="space-y-4">
          <div style={{ borderBottom: `1px solid rgba(26, 22, 16, 0.16)`, paddingBottom: 16 }}>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 4 }}>Unique IPs</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{profile.digital_footprint?.unique_ips}</div>
          </div>
          <div style={{ borderBottom: `1px solid rgba(26, 22, 16, 0.16)`, paddingBottom: 16 }}>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 4 }}>Known Devices</div>
            <div style={{ fontSize: 14 }}>{profile.digital_footprint?.unique_devices.join(" · ")}</div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 12 }}>Recent Logins</div>
            <div className="space-y-2">
              {profile.digital_footprint?.recent_logins.slice(0, 6).map((l, i) => (
                <div key={i} style={{ fontSize: 11, display: "flex", justifyContent: "space-between", gap: 12, color: INK_DIM }}>
                  <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {l.city ?? "Unknown"}
                    {l.ip && <span style={{ color: "rgba(26,22,16,0.4)" }}> · {l.ip}</span>}
                    {l.carrier && <span style={{ color: "rgba(26,22,16,0.4)" }}> · {l.carrier}</span>}
                  </span>
                  <span style={{ flexShrink: 0 }}>{l.date.split("T")[0]}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </DashboardPanel>

      <DashboardPanel label="10 · Off-Platform Surveillance" accent={GRAVEYARD_ACCENT}>
        <SectionTitle accent={GRAVEYARD_ACCENT}>Activity Reported From Outside TikTok</SectionTitle>
        {(profile.ad_profile?.off_platform_events ?? 0) > 0 ? (
          <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
              <div style={{ fontSize: 56, fontWeight: 700, color: GRAVEYARD_ACCENT }}>
                {profile.ad_profile!.off_platform_events.toLocaleString()}
              </div>
              <div style={{ fontSize: 11, color: INK_DIM, textTransform: "uppercase" }}>events</div>
            </div>
            <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
              Websites and apps <em>outside</em> TikTok that reported your activity back to
              ByteDance through its business tools. This is the tracking you cannot see from
              inside the app — it follows you across the open web.
            </div>
          </>
        ) : (
          <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
            No off-platform activity records were found in this export. Either no third-party
            sites shared your behavior with TikTok, or this section was excluded from your download.
          </div>
        )}
      </DashboardPanel>

      {(profile.ad_profile?.shop_order_count ?? 0) > 0 && (
        <DashboardPanel label="11 · On-Platform Purchases" accent={MODULE_D}>
          <SectionTitle accent={MODULE_D}>What You Bought On TikTok Shop</SectionTitle>
          <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 12 }}>
            {profile.ad_profile!.shop_order_count} orders on file · first-party purchase intent
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {profile.ad_profile!.shop_products.slice(0, 10).map((p, i) => (
              <div key={i} style={{ fontSize: 11, color: INK_DIM, display: "flex", gap: 8 }}>
                <span style={{ color: "rgba(26,22,16,0.4)" }}>{String(i + 1).padStart(2, "0")}</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {p.length > 60 ? p.slice(0, 60).trimEnd() + "…" : p}
                </span>
              </div>
            ))}
          </div>
        </DashboardPanel>
      )}

      {(profile.ad_profile?.product_browsing_count ?? 0) > 0 && (
        <DashboardPanel label="12 · Shopping Intent" accent={VIBE_ACCENT}>
          <SectionTitle accent={VIBE_ACCENT}>Products You Considered</SectionTitle>
          <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 12 }}>
            {profile.ad_profile!.product_browsing_count.toLocaleString()} products browsed · intent without purchase
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {profile.ad_profile!.browsed_products.slice(0, 10).map((p, i) => (
              <div key={i} style={{ fontSize: 11, color: INK_DIM, display: "flex", gap: 8 }}>
                <span style={{ color: "rgba(26,22,16,0.4)" }}>{String(i + 1).padStart(2, "0")}</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {p.length > 60 ? p.slice(0, 60).trimEnd() + "…" : p}
                </span>
              </div>
            ))}
          </div>
        </DashboardPanel>
      )}

      {profile.demographics && (
        <div className="md:col-span-2">
          <DashboardPanel label="13 · Demographic Reconstruction" accent={ACCENT}>
            <SectionTitle>What TikTok Infers About You</SectionTitle>
            <DemographicPanel result={profile.demographics} />
          </DashboardPanel>
        </div>
      )}
    </div>
  );
}
