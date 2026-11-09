import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import FallbackImage, { initialsOf } from "./FallbackImage";

describe("FallbackImage", () => {
  it("renders the image when src is set", () => {
    const { container } = render(<FallbackImage src="/a.png" name="A. Isak" sizeClass="h-10 w-10" />);
    expect(container.querySelector("img")?.getAttribute("src")).toBe("/a.png");
    expect(screen.queryByText("AI")).toBeNull();
  });

  it("shows initials once the image fails", () => {
    const { container } = render(<FallbackImage src="/broken.png" name="A. Isak" sizeClass="h-10 w-10" />);
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("AI")).toBeTruthy();
  });

  it("shows initials with no src", () => {
    render(<FallbackImage name="Arsenal" kind="club" sizeClass="h-10 w-10" />);
    expect(screen.getByText("A")).toBeTruthy();
  });

  it("tries again when src changes", () => {
    const { container, rerender } = render(<FallbackImage src="/broken.png" name="A. Isak" sizeClass="h-10 w-10" />);
    fireEvent.error(container.querySelector("img")!);
    rerender(<FallbackImage src="/next.png" name="A. Isak" sizeClass="h-10 w-10" />);
    expect(container.querySelector("img")?.getAttribute("src")).toBe("/next.png");
  });

  it("never shows alt text", () => {
    const { container } = render(<FallbackImage src="/broken.png" name="A. Isak" sizeClass="h-10 w-10" />);
    expect(container.querySelector("img")?.getAttribute("alt")).toBe("");
    fireEvent.error(container.querySelector("img")!);
    expect(container.textContent).toBe("AI");
  });

  it("takes initials from the first and last words, ignoring punctuation", () => {
    expect(initialsOf("A. Isak")).toBe("AI");
    expect(initialsOf("Arsenal")).toBe("A");
    expect(initialsOf("Kevin De Bruyne")).toBe("KB");
    expect(initialsOf("  ")).toBe("?");
  });
});
