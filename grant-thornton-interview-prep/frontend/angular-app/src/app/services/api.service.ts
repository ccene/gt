import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';
import { Order } from '../models/order';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  private apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getOrders(): Observable<Order[]> {
    return this.http.get<Order[]>(`${this.apiUrl}/orders`).pipe(
      catchError((error) => {
        console.error('Error fetching orders:', error);
        return throwError(() => new Error('Failed to fetch orders'));
      })
    );
  }

  getOrderById(id: string): Observable<Order> {
    return this.http.get<Order>(`${this.apiUrl}/orders/${id}`).pipe(
      catchError((error) => throwError(() => new Error('Failed to fetch order')))
    );
  }

  submitOrder(order: Omit<Order, 'status' | 'createdAt' | 'updatedAt'>): Observable<Order> {
    const headers = new HttpHeaders({ 'Content-Type': 'application/json' });
    return this.http.post<Order>(`${this.apiUrl}/submitOrder`, order, { headers }).pipe(
      catchError((error) => throwError(() => new Error('Failed to submit order')))
    );
  }

  // TODO: Add updateOrder, deleteOrder, etc.
}
