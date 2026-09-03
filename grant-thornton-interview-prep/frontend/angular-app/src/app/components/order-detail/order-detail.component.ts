import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { Order } from '../../models/order';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Component({
  selector: 'app-order-detail',
  templateUrl: './order-detail.component.html',
  styleUrls: ['./order-detail.component.css'],
})
export class OrderDetailComponent implements OnInit {
  order$: Observable<Order | null>;
  loading = true;
  error: string | null = null;

  constructor(
    private route: ActivatedRoute,
    private apiService: ApiService
  ) {
    this.order$ = of(null);
  }

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadOrder(id);
    }
  }

  loadOrder(id: string): void {
    this.loading = true;
    this.error = null;
    this.order$ = this.apiService.getOrderById(id).pipe(
      catchError((error) => {
        this.error = error.message;
        this.loading = false;
        return of(null);
      })
    );
  }
}
