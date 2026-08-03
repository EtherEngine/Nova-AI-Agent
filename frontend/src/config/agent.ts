/** Central agent identity + example prompts (single source of truth). */

export const AGENT = {
  name: "Nova",
  tagline: "Demo",
  description:
    "Hi, ich bin Nova, ein KI-Agent – willkommen zur Demo. ",
} as const;

export interface ExamplePrompt {
  title: string;
  prompt: string;
}

export const EXAMPLE_PROMPTS: ExamplePrompt[] = [
  { title: "Rechnen", prompt: "Was ist 145 geteilt durch 5?" },
  { title: "Multiplikation", prompt: "Multipliziere 23 mit 17." },
  { title: "Uhrzeit", prompt: "Wie spät ist es gerade in Europe/Berlin?" },
  { title: "Zeitzonen", prompt: "Welches Datum ist jetzt in America/New_York?" },
];
