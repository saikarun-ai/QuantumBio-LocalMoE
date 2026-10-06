import asyncio

from quantumbio_moe.engine import LocalMoEEngine


async def main() -> None:
    engine = LocalMoEEngine()

    print("Executing offline local MoE inference query...")
    prompt = "Synthesize an optimized OpenQASM 3.0 circuit for evaluating a 6-qubit molecular Hamiltonian."

    response = await engine.generate(prompt=prompt, max_tokens=256)

    print("\nLocal MoE Response:")
    print(response.text)
    print(f"\nRouted expert: {response.expert}")
    print(f"Generation Speed: {response.tokens_per_second:.2f} tok/s")

    await engine.close()


if __name__ == "__main__":
    asyncio.run(main())