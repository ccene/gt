import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { ReactiveFormsModule, FormArray, FormGroup } from '@angular/forms';
import { OrderFormComponent } from './order-form.component';
import { ApiService } from '../../services/api.service';
import { of, throwError } from 'rxjs';

describe('OrderFormComponent', () => {
  let component: OrderFormComponent;
  let fixture: ComponentFixture<OrderFormComponent>;
  let apiService: ApiService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [OrderFormComponent],
      imports: [
        HttpClientTestingModule,
        RouterTestingModule,
        ReactiveFormsModule
      ],
      providers: [ApiService]
    }).compileComponents();

    fixture = TestBed.createComponent(OrderFormComponent);
    component = fixture.componentInstance;
    apiService = TestBed.inject(ApiService);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize form with required fields', () => {
    expect(component.orderForm.contains('customerName')).toBeTruthy();
    expect(component.orderForm.contains('customerEmail')).toBeTruthy();
    expect(component.orderForm.contains('items')).toBeTruthy();
  });

  it('should add new item to form array', () => {
    const initialLength = component.items.length;
    component.addItem();
    expect(component.items.length).toBe(initialLength + 1);
  });

  it('should remove item from form array', () => {
    component.addItem();
    const initialLength = component.items.length;
    component.removeItem(0);
    expect(component.items.length).toBe(initialLength - 1);
  });

  it('should mark form as invalid when submitted with empty fields', () => {
    component.onSubmit();
    expect(component.submitted).toBeTruthy();
    expect(component.orderForm.invalid).toBeTruthy();
  });

  it('should submit form when valid', () => {
    component.orderForm.get('customerName')?.setValue('Test Customer');
    component.orderForm.get('customerEmail')?.setValue('test@example.com');
    
    const mockResponse = {
      id: 'order-1',
      customerName: 'Test Customer',
      customerEmail: 'test@example.com',
      items: [],
      status: 'pending',
      createdAt: new Date().toISOString()
    };
    
    jest.spyOn(apiService, 'submitOrder').mockReturnValue(of(mockResponse));
    jest.spyOn(component['router'], 'navigate');
    
    component.onSubmit();
    
    expect(apiService.submitOrder).toHaveBeenCalled();
  });
});
