import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { Order } from '../../models/order';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Component({
  selector: 'app-order-list',
  templateUrl: './order-list.component.html',
  styleUrls: ['./order-list.component.css'],
})
export class OrderListComponent implements OnInit {
  orders$: Observable<Order[]>;
  loading = true;
  error: string | null = null;

  constructor(private apiService: ApiService) {
    this.orders$ = of([]);
  }

  ngOnInit(): void {
    this.loadOrders();
  }

  loadOrders(): void {
    this.loading = true;
    this.error = null;
    this.orders$ = this.apiService.getOrders().pipe(
      catchError((error) => {
        this.error = error.message;
        this.loading = false;
        return of([]);
      })
    );
  }

  // TODO: Add refresh, delete, etc.
}
