export const dynamic = "force-dynamic";

type Product = { id: number; title: string; image_url: string };

async function getProducts(): Promise<Product[]> {
  const res = await fetch(`${process.env.BACKEND_URL}/api/products`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Backend responded ${res.status}`);
  return res.json();
}

export default async function CatalogPage() {
  const products = await getProducts();

  return (
    <main>
      <h1>Каталог</h1>
      <ul>
        {products.map((p) => (
          <li key={p.id}>
            <img src={p.image_url} alt={p.title} width={200} />
            <div>{p.title}</div>
          </li>
        ))}
      </ul>
    </main>
  );
}
