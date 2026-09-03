export interface Order {
  id: string;
  customerName: string;
  customerEmail: string;
  items: OrderItem[];
  status: 'pending' | 'processing' | 'completed' | 'failed';
  createdAt: string;
  updatedAt?: string;
}

export interface OrderItem {
  productId: string;
  productName: string;
  quantity: number;
  price: number;
}
