import { Component } from '@angular/core';
import { FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { OrderItem } from '../../models/order';

@Component({
  selector: 'app-order-form',
  templateUrl: './order-form.component.html',
  styleUrls: ['./order-form.component.css'],
})
export class OrderFormComponent {
  orderForm: FormGroup;
  submitted = false;
  error: string | null = null;

  constructor(
    private fb: FormBuilder,
    private apiService: ApiService,
    private router: Router
  ) {
    this.orderForm = this.fb.group({
      customerName: ['', [Validators.required, Validators.minLength(2)]],
      customerEmail: ['', [Validators.required, Validators.email]],
      items: this.fb.array([
        this.createItem()
      ])
    });
  }

  createItem(): FormGroup {
    return this.fb.group({
      productId: ['', Validators.required],
      productName: ['', Validators.required],
      quantity: [1, [Validators.required, Validators.min(1)]],
      price: [0, [Validators.required, Validators.min(0)]]
    });
  }

  get items() {
    return (this.orderForm.get('items') as FormArray).controls;
  }

  addItem(): void {
    (this.orderForm.get('items') as FormArray).push(this.createItem());
  }

  removeItem(index: number): void {
    (this.orderForm.get('items') as FormArray).removeAt(index);
  }

  onSubmit(): void {
    this.submitted = true;
    this.error = null;

    if (this.orderForm.invalid) {
      return;
    }

    const order = {
      id: `order-${Date.now()}`,
      ...this.orderForm.value,
      createdAt: new Date().toISOString()
    };

    this.apiService.submitOrder(order).subscribe({
      next: () => this.router.navigate(['/orders']),
      error: (err) => {
        this.error = err.message;
        this.submitted = false;
      }
    });
  }
}
