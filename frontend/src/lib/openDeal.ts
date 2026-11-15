/** A deal still running: in progress, or confirmed and waiting to complete
 *  (a closed window, a real-world move). The player is spoken for until it
 *  completes or falls through (backend deals/service.OPEN_DEAL_STATUSES). */
export function isOpenDeal(deal: { status: string } | null | undefined): boolean {
  return deal?.status === "IN_PROGRESS" || deal?.status === "PENDING_COMPLETION";
}
