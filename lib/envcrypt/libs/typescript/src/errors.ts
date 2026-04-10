export class EnvcryptError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvcryptError";
  }
}
