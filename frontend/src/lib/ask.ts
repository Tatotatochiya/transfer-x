/** The Ask TransferX page, opened about one player, offer or deal ("Ask about this"). */
export function askAboutPath(type: "player" | "offer" | "deal", id: string, name: string): string {
  return `/ask?${new URLSearchParams({ about: type, id, name })}`;
}
